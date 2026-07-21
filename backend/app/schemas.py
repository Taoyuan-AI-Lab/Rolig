from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def require_https(url: AnyHttpUrl) -> AnyHttpUrl:
    if url.scheme != "https":
        raise ValueError("media URLs must use HTTPS")
    return url


HttpsUrl = Annotated[AnyHttpUrl, AfterValidator(require_https)]


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class MemeStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class MemeCreateRequest(APIModel):
    creator_id: UUID
    media_url: HttpsUrl
    media_type: MediaType
    analysis_image_url: HttpsUrl | None = None

    @model_validator(mode="after")
    def require_video_frame(self) -> "MemeCreateRequest":
        if self.media_type is MediaType.VIDEO and self.analysis_image_url is None:
            raise ValueError("analysis_image_url is required for video memes")
        return self

    @property
    def visual_url(self) -> str:
        return str(self.analysis_image_url or self.media_url)


class MemeAnalysis(APIModel):
    summary: str = Field(min_length=1, max_length=500)
    tags: list[str] = Field(min_length=1, max_length=12)
    humor_style: str = Field(min_length=1, max_length=80)
    toxicity_score: float = Field(ge=0, le=1)
    is_safe: bool

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))
        if not normalized:
            raise ValueError("at least one non-empty tag is required")
        return normalized


class MemeResponse(APIModel):
    id: UUID
    creator_id: UUID
    media_url: str
    media_type: MediaType
    status: MemeStatus
    tags: list[str]
    summary: str
    humor_style: str
    toxicity_score: float
    created_at: datetime


class FeedWeights(APIModel):
    w1: float = Field(default=1.0, ge=0, le=100)
    w2: float = Field(default=10.0, ge=0, le=100)
    w3: float = Field(default=15.0, ge=0, le=100)


class FeedItem(APIModel):
    id: UUID
    creator_id: UUID
    media_url: str
    media_type: MediaType
    tags: list[str]
    summary: str
    humor_style: str
    score: float
    similarity: float | None
    created_at: datetime


class FeedResponse(APIModel):
    user_id: UUID
    items: list[FeedItem]
    cache_hit: bool


class ClientFeedItem(APIModel):
    id: UUID
    url: str
    type: MediaType
    tags: list[str]
    score: float = Field(ge=0, le=1)


class ClientFeedResponse(APIModel):
    items: list[ClientFeedItem]
    next_cursor: str | None = Field(serialization_alias="nextCursor")
