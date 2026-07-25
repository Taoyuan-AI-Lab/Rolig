import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status
from redis.exceptions import RedisError

from app.auth import CurrentUserDep
from app.dependencies import DatabaseDep, OpenAIDep, R2StorageDep, RedisDep, SettingsDep
from app.media_pipeline import (
    process_upload,
    validate_upload_declaration,
    verify_signature_bytes,
)
from app.repository import (
    begin_upload_processing,
    create_upload_session,
    get_upload_session,
    get_upload_usage,
)
from app.upload_schemas import (
    UploadCompleteRequest,
    UploadDatabaseStatus,
    UploadPresignRequest,
    UploadPresignResponse,
    UploadResult,
    UploadStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/uploads", tags=["uploads"])
UploadIdPath = Annotated[
    str,
    Path(pattern=r"^upl_[A-Za-z0-9_-]{20,64}$"),
]

CONTENT_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}


async def _enforce_rate_limit(
    redis: RedisDep,
    *,
    user_id: UUID,
    limit: int,
) -> None:
    window = int(datetime.now(UTC).timestamp()) // 3600
    key = f"rolig:upload-rate:v1:{user_id}:{window}"
    try:
        async with redis.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, 3700)
            count, _ = await pipeline.execute()
    except RedisError as exc:
        logger.warning("Upload rate limiter unavailable", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="upload service is temporarily unavailable",
        ) from exc
    if int(count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="upload rate limit exceeded",
            headers={"Retry-After": "3600"},
        )


def _result_from_row(row: dict[str, object]) -> UploadResult:
    database_status = str(row["status"])
    public_status = {
        UploadDatabaseStatus.PENDING_UPLOAD.value: UploadStatus.PROCESSING,
        UploadDatabaseStatus.PROCESSING.value: UploadStatus.PROCESSING,
        UploadDatabaseStatus.READY.value: UploadStatus.READY,
        UploadDatabaseStatus.REJECTED.value: UploadStatus.REJECTED,
    }[database_status]
    raw_meme_id = row.get("meme_id")
    return UploadResult(
        upload_id=str(row["upload_id"]),
        meme_id=UUID(str(raw_meme_id)) if raw_meme_id else None,
        status=public_status,
        message=str(row["message"]) if row.get("message") else None,
    )


def _authorize_upload(
    row: dict[str, object],
    user: CurrentUserDep,
    *,
    allow_admin: bool,
) -> None:
    if UUID(str(row["uploader_id"])) != user.id and not (allow_admin and user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")


@router.post(
    "/presign",
    response_model=UploadPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_upload(
    payload: UploadPresignRequest,
    user: CurrentUserDep,
    db: DatabaseDep,
    redis: RedisDep,
    storage: R2StorageDep,
    settings: SettingsDep,
) -> UploadPresignResponse:
    try:
        validate_upload_declaration(
            content_type=payload.content_type,
            media_type=payload.media_type.value,
            size_bytes=payload.size_bytes,
            image_max_bytes=settings.upload_image_max_bytes,
            video_max_bytes=settings.upload_video_max_bytes,
        )
    except OverflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="media exceeds the upload size limit",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported media type",
        ) from exc

    await _enforce_rate_limit(
        redis,
        user_id=user.id,
        limit=settings.upload_rate_limit_per_hour,
    )
    usage = await get_upload_usage(db, user.id)
    if usage + payload.size_bytes > settings.upload_quota_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="account storage quota exceeded",
        )

    opaque = secrets.token_urlsafe(24)
    upload_id = f"upl_{opaque}"
    extension = CONTENT_EXTENSIONS[payload.content_type]
    object_key = f"quarantine/uploads/{user.id}/{secrets.token_urlsafe(32)}.{extension}"
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.upload_url_ttl_seconds)
    try:
        upload_url = await storage.create_put_url(
            object_key=object_key,
            content_type=payload.content_type,
            expires_in=settings.upload_url_ttl_seconds,
        )
        await create_upload_session(
            db,
            upload_id=upload_id,
            uploader_id=user.id,
            object_key=object_key,
            payload=payload,
            expires_at=expires_at,
            quota_bytes=settings.upload_quota_bytes,
        )
    except OverflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="account storage quota exceeded",
        ) from exc
    except Exception as exc:
        logger.exception("Could not create upload session")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="upload service is temporarily unavailable",
        ) from exc

    return UploadPresignResponse(
        upload_id=upload_id,
        upload_url=upload_url,
        headers={"Content-Type": payload.content_type},
        expires_at=expires_at,
    )


@router.post("/{upload_id}/complete", response_model=UploadResult)
async def complete_upload(
    upload_id: UploadIdPath,
    payload: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUserDep,
    db: DatabaseDep,
    storage: R2StorageDep,
    openai_client: OpenAIDep,
    settings: SettingsDep,
) -> UploadResult:
    row = await get_upload_session(db, upload_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    _authorize_upload(row, user, allow_admin=False)
    if row["status"] != UploadDatabaseStatus.PENDING_UPLOAD.value:
        return _result_from_row(row)
    if row["expires_at"] < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="upload session has expired",
        )

    try:
        stored = await storage.head(str(row["object_key"]))
        if stored.content_length != int(row["declared_size_bytes"]):
            raise ValueError("uploaded size does not match the upload session")
        if stored.content_type.split(";", 1)[0].strip().lower() != row["declared_content_type"]:
            raise ValueError("uploaded content type does not match the upload session")
        header = await storage.read_prefix(str(row["object_key"]))
        verify_signature_bytes(header, str(row["declared_content_type"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.warning("Uploaded object verification failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="uploaded object could not be verified",
        ) from exc

    processing = await begin_upload_processing(
        db,
        upload_id=upload_id,
        uploader_id=user.id,
        actual_size_bytes=stored.content_length,
        attribution=payload.attribution,
    )
    if processing.pop("_started", False):
        background_tasks.add_task(
            process_upload,
            db=db,
            storage=storage,
            openai_client=openai_client,
            settings=settings,
            upload=processing,
            attribution=payload.attribution,
        )
    return _result_from_row(processing)


@router.get("/{upload_id}", response_model=UploadResult)
async def get_upload_status(
    upload_id: UploadIdPath,
    user: CurrentUserDep,
    db: DatabaseDep,
) -> UploadResult:
    row = await get_upload_session(db, upload_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    _authorize_upload(row, user, allow_admin=True)
    return _result_from_row(row)
