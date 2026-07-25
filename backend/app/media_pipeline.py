import asyncio
import hashlib
import logging
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
import openai
from imageio_ffmpeg import get_ffmpeg_exe
from openai import AsyncOpenAI
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.repository import publish_upload, record_sanitized_upload, reject_upload
from app.services import analyze_meme, create_embedding
from app.storage import R2Storage
from app.upload_schemas import UploadAttribution

logger = logging.getLogger(__name__)


ALLOWED_MEDIA: dict[str, tuple[str, int]] = {
    "image/jpeg": ("image", 15_728_640),
    "image/png": ("image", 15_728_640),
    "image/webp": ("image", 15_728_640),
    "video/mp4": ("video", 209_715_200),
    "video/quicktime": ("video", 209_715_200),
    "video/webm": ("video", 209_715_200),
}


@dataclass(frozen=True, slots=True)
class ProcessedMedia:
    media_path: Path
    content_type: str
    extension: str
    analysis_path: Path


def validate_upload_declaration(
    *,
    content_type: str,
    media_type: str,
    size_bytes: int,
    image_max_bytes: int,
    video_max_bytes: int,
) -> None:
    allowed = ALLOWED_MEDIA.get(content_type)
    if allowed is None or allowed[0] != media_type:
        raise ValueError("unsupported media type")
    maximum = image_max_bytes if media_type == "image" else video_max_bytes
    if size_bytes > maximum:
        raise OverflowError("media exceeds the upload size limit")


def verify_signature(path: Path, content_type: str) -> None:
    with path.open("rb") as source:
        header = source.read(16)
    verify_signature_bytes(header, content_type)


def verify_signature_bytes(header: bytes, content_type: str) -> None:
    valid = {
        "image/jpeg": header.startswith(b"\xff\xd8\xff"),
        "image/png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        "video/mp4": header[4:8] == b"ftyp",
        "video/quicktime": header[4:8] == b"ftyp",
        "video/webm": header.startswith(b"\x1aE\xdf\xa3"),
    }.get(content_type, False)
    if not valid:
        raise ValueError("uploaded bytes do not match the declared media type")


def _sanitize_image(source: Path, destination: Path, analysis_path: Path) -> str:
    try:
        with Image.open(source) as opened:
            opened.verify()
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((4096, 4096))
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            if has_alpha:
                image.convert("RGBA").save(destination, "PNG", optimize=True)
                content_type = "image/png"
            else:
                image.convert("RGB").save(
                    destination,
                    "JPEG",
                    quality=90,
                    optimize=True,
                    progressive=True,
                )
                content_type = "image/jpeg"
            analysis_image = image.convert("RGB")
            analysis_image.thumbnail((1280, 1280))
            analysis_image.save(analysis_path, "JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("uploaded image could not be decoded safely") from exc
    return content_type


async def _run_process(*args: str, max_seconds: float = 300) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=max_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise ValueError("media processing timed out") from None
    if process.returncode != 0:
        logger.warning("Media tool failed: %s", stderr.decode(errors="replace")[-1000:])
        raise ValueError("uploaded video could not be processed")
    return stdout


async def _sanitize_video(
    source: Path,
    destination: Path,
    analysis_path: Path,
    *,
    ffmpeg_binary: str,
) -> None:
    await _run_process(
        ffmpeg_binary,
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    )
    await _run_process(
        ffmpeg_binary,
        "-nostdin",
        "-y",
        "-ss",
        "1",
        "-i",
        str(destination),
        "-frames:v",
        "1",
        "-vf",
        "scale='min(1280,iw)':-2",
        str(analysis_path),
    )
    with destination.open("rb") as output:
        header = output.read(16)
    if header[4:8] != b"ftyp":
        raise ValueError("processed video is not an approved streaming format")


async def sanitize_media(
    source: Path,
    *,
    media_type: str,
    ffmpeg_binary: str,
    work_dir: Path,
) -> ProcessedMedia:
    analysis_path = work_dir / "analysis.jpg"
    if media_type == "image":
        destination = work_dir / "sanitized"
        content_type = await asyncio.to_thread(
            _sanitize_image,
            source,
            destination,
            analysis_path,
        )
        extension = "png" if content_type == "image/png" else "jpg"
        final_path = work_dir / f"sanitized.{extension}"
        await asyncio.to_thread(destination.replace, final_path)
        return ProcessedMedia(final_path, content_type, extension, analysis_path)

    destination = work_dir / "sanitized.mp4"
    await _sanitize_video(
        source,
        destination,
        analysis_path,
        ffmpeg_binary=ffmpeg_binary,
    )
    return ProcessedMedia(destination, "video/mp4", "mp4", analysis_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


async def process_upload(
    *,
    db: asyncpg.Pool,
    storage: R2Storage,
    openai_client: AsyncOpenAI | None,
    settings: Settings,
    upload: dict[str, object],
    attribution: UploadAttribution,
) -> None:
    upload_id = str(upload["upload_id"])
    source_key = str(upload["object_key"])
    meme_id = UUID(str(upload["meme_id"]))
    uploader_id = UUID(str(upload["uploader_id"]))
    try:
        with tempfile.TemporaryDirectory(prefix="rolig-upload-") as temporary:
            work_dir = Path(temporary)
            source_path = work_dir / "source"
            await storage.download_to(source_key, source_path)
            verify_signature(source_path, str(upload["declared_content_type"]))
            processed = await sanitize_media(
                source_path,
                media_type=str(upload["media_type"]),
                ffmpeg_binary=(
                    settings.ffmpeg_binary
                    or await asyncio.to_thread(get_ffmpeg_exe)
                ),
                work_dir=work_dir,
            )
            token = secrets.token_urlsafe(24)
            private_media_key = f"quarantine/processed/{token}.{processed.extension}"
            private_frame_key = f"quarantine/processed/{token}.analysis.jpg"
            await storage.upload_file(
                processed.media_path,
                private_media_key,
                content_type=processed.content_type,
            )
            await storage.upload_file(
                processed.analysis_path,
                private_frame_key,
                content_type="image/jpeg",
            )
            content_sha256 = await asyncio.to_thread(_sha256, processed.media_path)
            byte_size = processed.media_path.stat().st_size
            await record_sanitized_upload(
                db,
                upload_id=upload_id,
                media_object_key=private_media_key,
                analysis_object_key=private_frame_key,
                content_type=processed.content_type,
                byte_size=byte_size,
                content_sha256=content_sha256,
            )
            await storage.delete(source_key)

            if not settings.ai_analysis_enabled or openai_client is None:
                logger.info("Upload %s sanitized and held for moderation", upload_id)
                return

            analysis_url = await storage.create_get_url(object_key=private_frame_key)
            analysis = await analyze_meme(
                openai_client,
                model=settings.openai_analysis_model,
                image_url=analysis_url,
            )
            if not analysis.is_safe:
                await storage.delete(private_media_key)
                await storage.delete(private_frame_key)
                await reject_upload(db, upload_id=upload_id, message="Content rejected")
                return
            embedding = await create_embedding(
                openai_client,
                model=settings.openai_embedding_model,
                analysis=analysis,
            )
            public_prefix = f"media/{meme_id}"
            public_media_key = f"{public_prefix}/content.{processed.extension}"
            public_frame_key = f"{public_prefix}/analysis.jpg"
            await storage.upload_file(
                processed.media_path,
                public_media_key,
                content_type=processed.content_type,
                cache_control="public, max-age=31536000, immutable",
                public=True,
            )
            await storage.upload_file(
                processed.analysis_path,
                public_frame_key,
                content_type="image/jpeg",
                cache_control="public, max-age=31536000, immutable",
                public=True,
            )
            await publish_upload(
                db,
                upload_id=upload_id,
                meme_id=meme_id,
                uploader_id=uploader_id,
                public_url=storage.public_url(public_media_key),
                analysis_image_url=storage.public_url(public_frame_key),
                analysis=analysis,
                embedding=embedding,
                analysis_model=settings.openai_analysis_model,
                embedding_model=settings.openai_embedding_model,
                object_key=public_media_key,
                original_filename=str(upload["original_filename"]),
                content_sha256=content_sha256,
                content_type=processed.content_type,
                byte_size=byte_size,
                attribution=attribution,
            )
            await storage.delete(private_media_key)
            await storage.delete(private_frame_key)
    except (ValueError, FileNotFoundError):
        logger.warning("Upload validation failed for %s", upload_id, exc_info=True)
        await reject_upload(db, upload_id=upload_id, message="Invalid media")
    except openai.APIError:
        logger.warning("Moderation is temporarily unavailable for %s", upload_id, exc_info=True)
    except Exception:
        logger.exception("Upload processing failed for %s", upload_id)
