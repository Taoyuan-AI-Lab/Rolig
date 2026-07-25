import argparse
import asyncio
import hashlib
import json
import math
import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

import aioboto3
import asyncpg
import httpx
from botocore.exceptions import ClientError
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

from app.schemas import MediaType

EMBEDDING_DIMENSION = 1536
MAX_ASSET_BYTES = 200 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    MediaType.IMAGE: {"image/gif", "image/jpeg", "image/png", "image/webp"},
    MediaType.VIDEO: {"video/mp4", "video/quicktime", "video/webm"},
}


def require_https(url: AnyHttpUrl) -> AnyHttpUrl:
    if url.scheme != "https":
        raise ValueError("URLs must use HTTPS")
    return url


HttpsUrl = Annotated[AnyHttpUrl, AfterValidator(require_https)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PermissionBasis(StrEnum):
    ORIGINAL = "original"
    DIRECT_PERMISSION = "direct_permission"
    LICENSE = "license"
    PUBLIC_DOMAIN = "public_domain"


class AssetRights(StrictModel):
    attribution_text: str = Field(min_length=1, max_length=500)
    source_url: HttpsUrl | Literal["N/A"]
    permission_basis: PermissionBasis
    permission_notes: str = Field(min_length=1, max_length=2000)
    license_name: str | None = Field(default=None, min_length=1, max_length=200)
    license_url: HttpsUrl | None = None

    @model_validator(mode="after")
    def require_license_metadata(self) -> "AssetRights":
        if self.permission_basis is PermissionBasis.LICENSE:
            if not self.license_name or self.license_url is None:
                raise ValueError("licensed assets require license_name and license_url")
        return self


class DemoAsset(StrictModel):
    id: UUID
    creator_id: UUID
    file: str = Field(min_length=1, max_length=240)
    media_type: MediaType
    content_type: str = Field(min_length=1, max_length=100)
    tags: list[str] = Field(min_length=1, max_length=12)
    summary: str = Field(min_length=1, max_length=500)
    humor_style: str = Field(min_length=1, max_length=80)
    toxicity_score: float = Field(default=0, ge=0, le=1)
    approved_for_demo: Literal[True]
    rights: AssetRights
    like_count: int = Field(default=0, ge=0)
    view_count: int = Field(default=0, ge=0)
    music_title: str | None = Field(default=None, min_length=1, max_length=200)
    object_key: str | None = Field(default=None, min_length=1, max_length=900)

    @field_validator("file")
    @classmethod
    def validate_relative_file(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("file must be a safe path relative to the assets directory")
        return path.as_posix()

    @field_validator("object_key")
    @classmethod
    def validate_object_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/").lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise ValueError("object_key must be a safe relative R2 key")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))
        if not normalized:
            raise ValueError("at least one non-empty tag is required")
        return normalized

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str, info: Any) -> str:
        media_type = info.data.get("media_type")
        if media_type is not None and value.lower() not in ALLOWED_CONTENT_TYPES[media_type]:
            raise ValueError(f"{value} is not allowed for {media_type.value} assets")
        return value.lower()

    def resolved_object_key(self) -> str:
        if self.object_key:
            return self.object_key
        suffix = Path(self.file).suffix.lower()
        return f"demo/{self.id}{suffix}"


class DemoManifest(StrictModel):
    version: Literal[1]
    assets: list[DemoAsset] = Field(min_length=1, max_length=100)

    @field_validator("assets")
    @classmethod
    def require_unique_assets(cls, assets: list[DemoAsset]) -> list[DemoAsset]:
        ids = [asset.id for asset in assets]
        keys = [asset.resolved_object_key() for asset in assets]
        if len(ids) != len(set(ids)):
            raise ValueError("asset ids must be unique")
        if len(keys) != len(set(keys)):
            raise ValueError("R2 object keys must be unique")
        return assets


class DemoDataSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)
    r2_account_id: str = Field(min_length=1)
    r2_access_key_id: str = Field(min_length=1)
    r2_secret_access_key: str = Field(min_length=1)
    r2_bucket_name: str = Field(min_length=1)
    r2_public_base_url: HttpsUrl

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


class PreparedAsset(StrictModel):
    manifest: DemoAsset
    path: Path
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _load_manifest_sync(path: Path) -> DemoManifest:
    return DemoManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _hash_file_sync(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            byte_size += len(chunk)
            if byte_size > MAX_ASSET_BYTES:
                raise ValueError(f"{path.name} exceeds the {MAX_ASSET_BYTES}-byte demo limit")
            digest.update(chunk)
    if byte_size == 0:
        raise ValueError(f"{path.name} is empty")
    return byte_size, digest.hexdigest()


def _sniff_content_type_sync(path: Path) -> str:
    with path.open("rb") as file_handle:
        header = file_handle.read(16)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if header[4:8] == b"ftyp":
        return "video/quicktime" if header[8:12] == b"qt  " else "video/mp4"
    raise ValueError(f"{path.name} is not a recognized supported image or video")


async def load_and_prepare_manifest(
    manifest_path: Path,
    assets_dir: Path,
) -> tuple[DemoManifest, list[PreparedAsset]]:
    manifest = await asyncio.to_thread(_load_manifest_sync, manifest_path)
    resolved_root = await asyncio.to_thread(assets_dir.resolve, strict=True)
    prepared: list[PreparedAsset] = []
    for asset in manifest.assets:
        asset_path = await asyncio.to_thread(
            (resolved_root / asset.file).resolve,
            strict=True,
        )
        if resolved_root not in asset_path.parents:
            raise ValueError(f"{asset.file} resolves outside the assets directory")
        sniffed_content_type = await asyncio.to_thread(_sniff_content_type_sync, asset_path)
        if sniffed_content_type != asset.content_type:
            raise ValueError(
                f"{asset.file} is {sniffed_content_type}, not {asset.content_type}"
            )
        byte_size, sha256 = await asyncio.to_thread(_hash_file_sync, asset_path)
        prepared.append(
            PreparedAsset(
                manifest=asset,
                path=asset_path,
                byte_size=byte_size,
                sha256=sha256,
            )
        )
    return manifest, prepared


def create_demo_embedding(asset: DemoAsset) -> list[float]:
    text = " ".join((asset.summary, asset.humor_style, *asset.tags)).lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ValueError("cannot create an embedding from empty demo metadata")
    return [value / norm for value in vector]


def _vector_literal(embedding: Sequence[float]) -> str:
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(f"embedding must contain {EMBEDDING_DIMENSION} values")
    return "[" + ",".join(format(value, ".9g") for value in embedding) + "]"


async def upload_asset(
    s3_client: Any,
    *,
    settings: DemoDataSettings,
    prepared: PreparedAsset,
) -> str:
    asset = prepared.manifest
    object_key = asset.resolved_object_key()
    try:
        existing = await s3_client.head_object(
            Bucket=settings.r2_bucket_name,
            Key=object_key,
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
            raise
    else:
        existing_hash = existing.get("Metadata", {}).get("sha256")
        if existing_hash != prepared.sha256:
            raise ValueError(f"R2 object {object_key} exists with different content")
        if existing.get("ContentLength") != prepared.byte_size:
            raise ValueError(f"R2 object {object_key} has an unexpected size")
        return f"{str(settings.r2_public_base_url).rstrip('/')}/{quote(object_key, safe='/')}"

    await s3_client.upload_file(
        str(prepared.path),
        settings.r2_bucket_name,
        object_key,
        ExtraArgs={
            "CacheControl": "public, max-age=31536000, immutable",
            "ContentDisposition": "inline",
            "ContentType": asset.content_type,
            "Metadata": {
                "meme-id": str(asset.id),
                "sha256": prepared.sha256,
            },
        },
    )
    uploaded = await s3_client.head_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
    )
    if uploaded.get("ContentLength") != prepared.byte_size:
        raise RuntimeError(f"R2 verification failed for {object_key}")
    return f"{str(settings.r2_public_base_url).rstrip('/')}/{quote(object_key, safe='/')}"


async def verify_public_media(url: str, asset: DemoAsset) -> None:
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"Range": "bytes=0-0"})
    if response.status_code not in {200, 206}:
        raise RuntimeError(f"public R2 verification returned HTTP {response.status_code}")
    returned_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if returned_type != asset.content_type:
        raise RuntimeError(
            f"public R2 content type is {returned_type or 'missing'}, expected {asset.content_type}"
        )
    if asset.media_type is MediaType.VIDEO:
        accepts_ranges = response.headers.get("accept-ranges", "").lower()
        if response.status_code != 206 and accepts_ranges != "bytes":
            raise RuntimeError("public video does not advertise byte-range streaming")


async def upsert_demo_record(
    connection: asyncpg.Connection,
    *,
    prepared: PreparedAsset,
    media_url: str,
) -> None:
    asset = prepared.manifest
    rights = asset.rights
    embedding = _vector_literal(create_demo_embedding(asset))
    async with connection.transaction():
        await connection.execute(
            """
            INSERT INTO memes (
                id, creator_id, media_url, media_type, status, tags, summary, humor_style,
                toxicity_score, embedding, analysis_model, embedding_model, like_count,
                view_count, music_title
            )
            VALUES (
                $1, $2, $3, $4, 'ready', $5, $6, $7, $8, $9::vector,
                'curated-manual-v1', 'rolig-hash-embedding-v1', $10, $11, $12
            )
            ON CONFLICT (id) DO UPDATE SET
                creator_id = EXCLUDED.creator_id,
                media_url = EXCLUDED.media_url,
                media_type = EXCLUDED.media_type,
                status = EXCLUDED.status,
                tags = EXCLUDED.tags,
                summary = EXCLUDED.summary,
                humor_style = EXCLUDED.humor_style,
                toxicity_score = EXCLUDED.toxicity_score,
                embedding = EXCLUDED.embedding,
                analysis_model = EXCLUDED.analysis_model,
                embedding_model = EXCLUDED.embedding_model,
                like_count = EXCLUDED.like_count,
                view_count = EXCLUDED.view_count,
                music_title = EXCLUDED.music_title,
                updated_at = now()
            """,
            asset.id,
            asset.creator_id,
            media_url,
            asset.media_type.value,
            asset.tags,
            asset.summary,
            asset.humor_style,
            asset.toxicity_score,
            embedding,
            asset.like_count,
            asset.view_count,
            asset.music_title,
        )
        await connection.execute(
            """
            INSERT INTO meme_asset_rights (
                meme_id, object_key, original_filename, content_sha256, content_type,
                byte_size, attribution_text, source_url, permission_basis, license_name,
                license_url, permission_notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (meme_id) DO UPDATE SET
                object_key = EXCLUDED.object_key,
                original_filename = EXCLUDED.original_filename,
                content_sha256 = EXCLUDED.content_sha256,
                content_type = EXCLUDED.content_type,
                byte_size = EXCLUDED.byte_size,
                attribution_text = EXCLUDED.attribution_text,
                source_url = EXCLUDED.source_url,
                permission_basis = EXCLUDED.permission_basis,
                license_name = EXCLUDED.license_name,
                license_url = EXCLUDED.license_url,
                permission_notes = EXCLUDED.permission_notes,
                updated_at = now()
            """,
            asset.id,
            asset.resolved_object_key(),
            prepared.path.name,
            prepared.sha256,
            asset.content_type,
            prepared.byte_size,
            rights.attribution_text,
            str(rights.source_url),
            rights.permission_basis.value,
            rights.license_name,
            str(rights.license_url) if rights.license_url else None,
            rights.permission_notes,
        )


async def invalidate_feed_cache(redis: Redis) -> int:
    keys: list[str] = []
    async for key in redis.scan_iter(match="rolig:feed:*", count=100):
        keys.append(str(key))
    if keys:
        await redis.delete(*keys)
    return len(keys)


async def ingest_demo_data(
    manifest_path: Path,
    assets_dir: Path,
    *,
    dry_run: bool,
) -> dict[str, object]:
    _, prepared_assets = await load_and_prepare_manifest(manifest_path, assets_dir)
    if dry_run:
        return {
            "validated": len(prepared_assets),
            "totalBytes": sum(asset.byte_size for asset in prepared_assets),
            "uploaded": 0,
        }

    settings = DemoDataSettings()  # type: ignore[call-arg]
    connection = await asyncpg.connect(
        settings.database_url,
        command_timeout=15,
        statement_cache_size=0,
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    uploaded_urls: list[str] = []
    session = aioboto3.Session()
    try:
        async with session.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        ) as s3_client:
            for prepared in prepared_assets:
                media_url = await upload_asset(
                    s3_client,
                    settings=settings,
                    prepared=prepared,
                )
                await verify_public_media(media_url, prepared.manifest)
                await upsert_demo_record(
                    connection,
                    prepared=prepared,
                    media_url=media_url,
                )
                uploaded_urls.append(media_url)
        invalidated = await invalidate_feed_cache(redis)
    finally:
        await redis.aclose()
        await connection.close()
    return {
        "validated": len(prepared_assets),
        "uploaded": len(uploaded_urls),
        "invalidatedFeedKeys": invalidated,
        "publicUrls": uploaded_urls,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and ingest approved Rolig demo assets into R2 and Supabase."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate local files and rights metadata without contacting providers.",
    )
    return parser


def main() -> None:
    arguments = _build_parser().parse_args()
    result = asyncio.run(
        ingest_demo_data(
            arguments.manifest,
            arguments.assets_dir,
            dry_run=arguments.dry_run,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
