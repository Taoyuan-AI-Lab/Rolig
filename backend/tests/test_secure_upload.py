import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image
from pydantic import ValidationError

from app import upload_router
from app.auth import AuthenticatedUser, verify_session_token
from app.media_pipeline import (
    _run_process,
    sanitize_media,
    validate_upload_declaration,
    verify_signature_bytes,
)
from app.schemas import MediaType
from app.upload_schemas import UploadPresignRequest


def _jwt(payload: dict[str, object], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    def encode(value: object) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    encoded_header = encode(header)
    encoded_payload = encode(payload)
    signature = hmac.new(
        secret.encode(),
        f"{encoded_header}.{encoded_payload}".encode(),
        hashlib.sha256,
    ).digest()
    return (
        f"{encoded_header}.{encoded_payload}."
        f"{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"
    )


def test_session_token_uses_signed_subject_and_admin_claim() -> None:
    user_id = uuid4()
    token = _jwt(
        {
            "sub": str(user_id),
            "exp": int(time.time()) + 300,
            "role": "authenticated",
            "app_metadata": {"role": "admin"},
        },
        "a-secure-test-secret-that-is-long-enough",
    )

    user = verify_session_token(token, "a-secure-test-secret-that-is-long-enough")

    assert user.id == user_id
    assert user.is_admin is True


def test_session_token_rejects_tampering() -> None:
    token = _jwt(
        {
            "sub": str(uuid4()),
            "exp": int(time.time()) + 300,
            "role": "authenticated",
        },
        "a-secure-test-secret-that-is-long-enough",
    )

    with pytest.raises(ValueError, match="invalid session token"):
        verify_session_token(f"{token[:-1]}x", "a-secure-test-secret-that-is-long-enough")


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
    settings = SimpleNamespace(
        upload_image_max_bytes=2048,
        upload_video_max_bytes=2048,
        upload_rate_limit_per_hour=20,
        upload_quota_bytes=4096,
        upload_url_ttl_seconds=300,
    )

    response = await upload_router.presign_upload(
        payload=payload,
        user=AuthenticatedUser(id=uuid4(), is_admin=False),
        db=object(),
        redis=object(),
        storage=FakeStorage(),
        settings=settings,
    )

    object_key = str(captured["object_key"])
    assert object_key.startswith("quarantine/uploads/")
    assert "chosen-name" not in object_key
    assert response.upload_id.startswith("upl_")
    assert response.headers == {"Content-Type": "video/mp4"}


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
