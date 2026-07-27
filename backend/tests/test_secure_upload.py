import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import BackgroundTasks, HTTPException
from imageio_ffmpeg import get_ffmpeg_exe
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm
from jwt.exceptions import PyJWKClientError
from PIL import Image
from pydantic import ValidationError

from app import media_pipeline, upload_router
from app.auth import AuthenticatedUser, verify_session_token
from app.config import Settings
from app.media_pipeline import (
    _run_process,
    sanitize_media,
    validate_upload_declaration,
    verify_signature_bytes,
)
from app.repository import create_upload_session
from app.schemas import MediaType
from app.storage import R2Storage, StoredObject
from app.upload_schemas import UploadCompleteRequest, UploadPresignRequest

TEST_ISSUER = "https://project-ref.supabase.co/auth/v1"
TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
TEST_PUBLIC_JWK = json.loads(ECAlgorithm.to_jwk(TEST_PRIVATE_KEY.public_key()))
TEST_PUBLIC_JWK.update({"alg": "ES256", "kid": "test-key", "use": "sig"})


class StaticJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        return PyJWK.from_dict(TEST_PUBLIC_JWK)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql://database.example/rolig",
        "r2_access_key_id": "test-access-key",
        "r2_account_id": "test-account",
        "r2_public_base_url": "https://media.example",
        "r2_secret_access_key": "test-secret-key",
        "redis_url": "rediss://redis.example",
        "supabase_url": "https://project-ref.supabase.co",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _claims(**overrides: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "aud": "authenticated",
        "exp": int(time.time()) + 300,
        "iss": TEST_ISSUER,
        "role": "authenticated",
        "sub": str(uuid4()),
    }
    claims.update(overrides)
    return claims


def _jwt(payload: dict[str, object]) -> str:
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": "test-key", "typ": "JWT"},
    )


def test_session_token_uses_verified_subject_and_admin_claim() -> None:
    user_id = uuid4()
    token = _jwt(
        _claims(
            sub=str(user_id),
            app_metadata={"role": "admin"},
        )
    )

    user = verify_session_token(
        token,
        jwks_client=StaticJwksClient(),
        issuer=TEST_ISSUER,
    )

    assert user.id == user_id
    assert user.is_admin is True


def test_session_token_rejects_tampering() -> None:
    token = _jwt(_claims())
    header, payload, signature = token.split(".")
    index = len(payload) // 2
    replacement = "A" if payload[index] != "A" else "B"
    tampered_payload = f"{payload[:index]}{replacement}{payload[index + 1 :]}"
    tampered_token = f"{header}.{tampered_payload}.{signature}"

    with pytest.raises(ValueError, match="invalid session token"):
        verify_session_token(
            tampered_token,
            jwks_client=StaticJwksClient(),
            issuer=TEST_ISSUER,
        )


@pytest.mark.parametrize(
    "claims",
    [
        _claims(aud="another-application"),
        _claims(exp=int(time.time()) - 1),
        _claims(iss="https://attacker.example/auth/v1"),
        _claims(role="service_role"),
        _claims(sub="not-a-uuid"),
    ],
)
def test_session_token_rejects_untrusted_claims(claims: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="invalid session token"):
        verify_session_token(
            _jwt(claims),
            jwks_client=StaticJwksClient(),
            issuer=TEST_ISSUER,
        )


def test_session_token_rejects_non_es256_algorithm() -> None:
    token = jwt.encode(
        _claims(),
        "a-secure-test-secret-that-is-long-enough",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )

    with pytest.raises(ValueError, match="invalid session token"):
        verify_session_token(
            token,
            jwks_client=StaticJwksClient(),
            issuer=TEST_ISSUER,
        )


def test_session_token_rejects_unknown_signing_key() -> None:
    class UnknownKeyClient:
        def get_signing_key_from_jwt(self, token: str) -> PyJWK:
            raise PyJWKClientError("unknown signing key")

    with pytest.raises(ValueError, match="invalid session token"):
        verify_session_token(
            _jwt(_claims()),
            jwks_client=UnknownKeyClient(),
            issuer=TEST_ISSUER,
        )


@pytest.mark.parametrize(
    "supabase_url",
    [
        "http://project-ref.supabase.co",
        "https://user:password@project-ref.supabase.co",
        "https://project-ref.supabase.co/rest/v1",
        "https://project-ref.supabase.co?redirect=https://attacker.example",
    ],
)
def test_supabase_url_requires_clean_https_origin(supabase_url: str) -> None:
    with pytest.raises(ValidationError, match="SUPABASE_URL"):
        _settings(supabase_url=supabase_url)


def test_supabase_url_accepts_project_origin() -> None:
    assert str(_settings().supabase_url) == "https://project-ref.supabase.co/"


def test_presign_schema_does_not_accept_creator_or_object_key() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UploadPresignRequest.model_validate(
            {
                "contentType": "video/mp4",
                "fileName": "reaction.mp4",
                "mediaType": "video",
                "sizeBytes": 1234,
                "creatorId": str(uuid4()),
                "objectKey": "published/attacker.mp4",
            }
        )


def test_upload_declaration_enforces_type_and_size() -> None:
    with pytest.raises(ValueError, match="unsupported media type"):
        validate_upload_declaration(
            content_type="image/png",
            media_type="video",
            size_bytes=10,
            image_max_bytes=100,
            video_max_bytes=100,
        )
    with pytest.raises(OverflowError, match="size limit"):
        validate_upload_declaration(
            content_type="video/mp4",
            media_type="video",
            size_bytes=101,
            image_max_bytes=100,
            video_max_bytes=100,
        )


def test_signature_verification_rejects_spoofed_media() -> None:
    verify_signature_bytes(b"\x89PNG\r\n\x1a\nmore-bytes", "image/png")

    with pytest.raises(ValueError, match="do not match"):
        verify_signature_bytes(b"<script>alert(1)", "image/png")


async def test_presigned_put_does_not_require_client_controlled_content_length() -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        async def generate_presigned_url(self, operation: str, **kwargs) -> str:
            captured["operation"] = operation
            captured.update(kwargs)
            return "https://signed.example/object"

    storage = R2Storage(
        account_id="account",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="public",
        quarantine_bucket_name="private",
        public_base_url="https://media.example",
    )

    @asynccontextmanager
    async def fake_client():
        yield FakeClient()

    storage._client = fake_client  # type: ignore[method-assign]
    await storage.create_put_url(
        object_key="quarantine/uploads/object.mp4",
        content_type="video/mp4",
        content_length=1234,
        expires_in=300,
    )

    params = captured["Params"]
    assert isinstance(params, dict)
    assert params["Bucket"] == "private"
    assert params["ContentType"] == "video/mp4"
    # Browsers and React Native control Content-Length themselves and cannot
    # reliably reproduce it as a signed header. The completion endpoint reads
    # the object metadata and rejects/deletes any declared-size mismatch.
    assert "ContentLength" not in params


async def test_image_processing_strips_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    image = Image.new("RGB", (20, 20), "red")
    image.save(source, "JPEG", exif=b"Exif\x00\x00unsafe-metadata")

    processed = await sanitize_media(
        source,
        media_type="image",
        ffmpeg_binary="ffmpeg",
        work_dir=tmp_path,
    )

    with Image.open(processed.media_path) as sanitized:
        assert sanitized.getexif() == {}
    assert processed.analysis_path.exists()


async def test_video_processing_outputs_streaming_mp4_and_frame(tmp_path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    source = tmp_path / "source.mp4"
    await _run_process(
        ffmpeg,
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x64:d=2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(source),
        max_seconds=30,
    )

    processed = await sanitize_media(
        source,
        media_type="video",
        ffmpeg_binary=ffmpeg,
        work_dir=tmp_path,
    )

    assert processed.content_type == "video/mp4"
    assert processed.media_path.read_bytes()[4:8] == b"ftyp"
    assert processed.analysis_path.stat().st_size > 0


async def test_video_processing_command_bounds_memory_and_dimensions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_run_process(*args: str, max_seconds: float = 300) -> bytes:
        calls.append(args)
        await asyncio.to_thread(Path(args[-1]).write_bytes, b"\x00\x00\x00\x18ftyp")
        return b""

    monkeypatch.setattr(media_pipeline, "_run_process", fake_run_process)
    await media_pipeline._sanitize_video(
        tmp_path / "source.mp4",
        tmp_path / "sanitized.mp4",
        tmp_path / "analysis.jpg",
        ffmpeg_binary="ffmpeg",
    )

    transcode = calls[0]
    assert transcode[transcode.index("-max_alloc") + 1] == str(64 * 1024 * 1024)
    assert transcode[transcode.index("-filter_threads") + 1] == "1"
    assert all(
        transcode[index + 1] == "1" for index, value in enumerate(transcode) if value == "-threads"
    )
    scale_filter = transcode[transcode.index("-vf") + 1]
    assert "min(1280,iw)" in scale_filter
    assert "min(1280,ih)" in scale_filter
    assert transcode[transcode.index("-preset") + 1] == "ultrafast"
    assert transcode[transcode.index("-tune") + 1] == "zerolatency"


async def test_video_processing_serializes_transcodes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    active = 0
    maximum_active = 0

    async def fake_sanitize_video(
        source: Path,
        destination: Path,
        analysis_path: Path,
        *,
        ffmpeg_binary: str,
    ) -> None:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1

    monkeypatch.setattr(media_pipeline, "_sanitize_video", fake_sanitize_video)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftyp")

    await asyncio.gather(
        *(
            sanitize_media(
                source,
                media_type="video",
                ffmpeg_binary="ffmpeg",
                work_dir=tmp_path / f"work-{index}",
            )
            for index in range(2)
        )
    )

    assert maximum_active == 1


async def test_presign_generates_opaque_server_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def no_rate_limit(*args, **kwargs) -> None:
        return None

    async def no_usage(*args, **kwargs) -> int:
        return 0

    async def capture_session(*args, **kwargs) -> None:
        captured.update(kwargs)

    class FakeStorage:
        async def create_put_url(self, **kwargs) -> str:
            captured.update(kwargs)
            return "https://signed.example/upload?signature=secret"

    monkeypatch.setattr(upload_router, "_enforce_rate_limit", no_rate_limit)
    monkeypatch.setattr(upload_router, "get_upload_usage", no_usage)
    monkeypatch.setattr(upload_router, "create_upload_session", capture_session)
    payload = UploadPresignRequest(
        content_type="video/mp4",
        file_name="../../chosen-name.mp4",
        media_type=MediaType.VIDEO,
        size_bytes=1024,
    )
    user = AuthenticatedUser(id=uuid4(), is_admin=False)
    settings = SimpleNamespace(
        upload_image_max_bytes=2048,
        upload_video_max_bytes=2048,
        upload_rate_limit_per_hour=20,
        upload_quota_bytes=4096,
        upload_url_ttl_seconds=300,
        upload_allowed_user_ids=(user.id,),
    )

    response = await upload_router.presign_upload(
        payload=payload,
        user=user,
        db=object(),
        redis=object(),
        storage=FakeStorage(),
        settings=settings,
    )

    object_key = str(captured["object_key"])
    assert object_key.startswith("quarantine/uploads/")
    assert "chosen-name" not in object_key
    assert captured["content_length"] == 1024
    assert response.upload_id.startswith("upl_")
    assert response.headers == {"Content-Type": "video/mp4"}


async def test_create_upload_session_uses_text_only_for_advisory_lock() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeTransaction:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *args: object) -> None:
            return None

    class FakeConnection:
        def transaction(self) -> FakeTransaction:
            return FakeTransaction()

        async def execute(self, query: str, *args: object) -> None:
            calls.append((query, args))

        async def fetchval(self, query: str, *args: object) -> int:
            calls.append((query, args))
            return 0

    class FakeAcquire:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *args: object) -> None:
            return None

    class FakePool:
        def acquire(self) -> FakeAcquire:
            return FakeAcquire()

    uploader_id = uuid4()
    payload = UploadPresignRequest(
        content_type="video/mp4",
        file_name="demo.mp4",
        media_type=MediaType.VIDEO,
        size_bytes=1024,
    )

    await create_upload_session(
        FakePool(),  # type: ignore[arg-type]
        upload_id="upl_abcdefghijklmnopqrstuvwxyz",
        uploader_id=uploader_id,
        object_key="quarantine/uploads/object.mp4",
        payload=payload,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        quota_bytes=4096,
    )

    assert calls[0][1] == (str(uploader_id),)
    assert calls[1][1] == (uploader_id,)
    assert calls[2][1][1] == uploader_id


async def test_presign_rejects_authenticated_user_outside_demo_allowlist() -> None:
    payload = UploadPresignRequest(
        content_type="video/mp4",
        file_name="demo.mp4",
        media_type=MediaType.VIDEO,
        size_bytes=1024,
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_router.presign_upload(
            payload=payload,
            user=AuthenticatedUser(id=uuid4(), is_admin=False),
            db=object(),
            redis=object(),
            storage=object(),
            settings=SimpleNamespace(upload_allowed_user_ids=()),
        )

    assert exc_info.value.status_code == 403


async def test_complete_deletes_and_rejects_size_mismatch(monkeypatch) -> None:
    user = AuthenticatedUser(id=uuid4(), is_admin=False)
    upload_id = "upl_abcdefghijklmnopqrstuvwxyz"
    deleted: list[str] = []
    rejected: list[tuple[str, str]] = []
    row = {
        "upload_id": upload_id,
        "uploader_id": user.id,
        "object_key": "quarantine/uploads/object.mp4",
        "declared_content_type": "video/mp4",
        "declared_size_bytes": 100,
        "status": "pending_upload",
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
    }

    async def fake_get_upload_session(*args, **kwargs):
        return row

    async def fake_reject_upload(*args, **kwargs) -> None:
        rejected.append((kwargs["upload_id"], kwargs["message"]))

    class FakeStorage:
        async def head(self, object_key: str) -> StoredObject:
            return StoredObject(content_length=101, content_type="video/mp4", etag=None)

        async def delete(self, object_key: str) -> None:
            deleted.append(object_key)

    monkeypatch.setattr(upload_router, "get_upload_session", fake_get_upload_session)
    monkeypatch.setattr(upload_router, "reject_upload", fake_reject_upload)
    payload = UploadCompleteRequest.model_validate(
        {
            "attribution": {
                "creatorName": "Rolig Official",
                "sourceUrl": "https://rolig.example/source",
                "license": "Original content",
                "permissionConfirmed": True,
            }
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_router.complete_upload(
            upload_id=upload_id,
            payload=payload,
            background_tasks=BackgroundTasks(),
            user=user,
            db=object(),
            storage=FakeStorage(),
            openai_client=None,
            settings=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 422
    assert deleted == ["quarantine/uploads/object.mp4"]
    assert rejected == [(upload_id, "Invalid media")]


def test_upload_result_uses_frontend_aliases() -> None:
    response = upload_router._result_from_row(
        {
            "upload_id": "upl_abcdefghijklmnopqrstuvwxyz",
            "meme_id": uuid4(),
            "status": "ready",
            "message": "Published",
        }
    )

    payload = response.model_dump(mode="json")

    assert set(payload) == {"uploadId", "memeId", "status", "message"}


def test_upload_owner_check_fails_closed() -> None:
    with pytest.raises(HTTPException) as exc_info:
        upload_router._authorize_upload(
            {"uploader_id": uuid4()},
            AuthenticatedUser(id=uuid4(), is_admin=False),
            allow_admin=False,
        )

    assert exc_info.value.status_code == 403
