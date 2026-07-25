from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.schemas import MediaType


class UploadAPIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
        str_strip_whitespace=True,
    )


class UploadLicense(StrEnum):
    PERMISSION_GRANTED = "Permission granted"
    ORIGINAL_CONTENT = "Original content"
    CREATIVE_COMMONS = "Creative Commons"
    PUBLIC_DOMAIN = "Public domain"


class UploadStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"


class UploadDatabaseStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"


class UploadPresignRequest(UploadAPIModel):
    content_type: str = Field(alias="contentType", min_length=1, max_length=100)
    file_name: str = Field(alias="fileName", min_length=1, max_length=255)
    media_type: MediaType = Field(alias="mediaType")
    size_bytes: int = Field(alias="sizeBytes", gt=0)


def require_https(url: AnyHttpUrl) -> AnyHttpUrl:
    if url.scheme != "https":
        raise ValueError("sourceUrl must use HTTPS")
    return url


SourceUrl = Annotated[AnyHttpUrl, AfterValidator(require_https)]


class UploadAttribution(UploadAPIModel):
    creator_name: str = Field(alias="creatorName", min_length=1, max_length=200)
    source_url: SourceUrl = Field(alias="sourceUrl")
    license: UploadLicense
    permission_confirmed: bool = Field(alias="permissionConfirmed")

    @model_validator(mode="after")
    def require_permission(self) -> "UploadAttribution":
        if not self.permission_confirmed:
            raise ValueError("permissionConfirmed must be true")
        return self


class UploadCompleteRequest(UploadAPIModel):
    attribution: UploadAttribution


class UploadPresignResponse(UploadAPIModel):
    upload_id: str = Field(alias="uploadId")
    upload_url: str = Field(alias="uploadUrl")
    headers: dict[str, str]
    expires_at: datetime = Field(alias="expiresAt")


class UploadResult(UploadAPIModel):
    upload_id: str = Field(alias="uploadId")
    meme_id: UUID | None = Field(alias="memeId")
    status: UploadStatus
    message: str | None
