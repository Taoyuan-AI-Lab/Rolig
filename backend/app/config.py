from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(min_length=1)
    openai_api_key: str | None = None
    ai_analysis_enabled: bool = False
    redis_url: str = Field(min_length=1)
    supabase_jwt_secret: SecretStr = Field(min_length=32)
    auth_cookie_name: str = Field(default="rolig_session", min_length=1, max_length=64)
    openai_analysis_model: str = "gpt-5.6"
    openai_embedding_model: str = "text-embedding-3-small"
    feed_cache_ttl_seconds: int = Field(default=60, ge=5, le=3600)
    media_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ()
    r2_account_id: str = Field(min_length=1)
    r2_access_key_id: SecretStr = Field(min_length=1)
    r2_secret_access_key: SecretStr = Field(min_length=1)
    r2_bucket_name: str = Field(default="rolig-media", min_length=1)
    r2_quarantine_bucket_name: str = Field(
        default="rolig-media-quarantine",
        min_length=1,
    )
    r2_public_base_url: str = Field(min_length=1)
    upload_url_ttl_seconds: int = Field(default=300, ge=60, le=300)
    upload_rate_limit_per_hour: int = Field(default=20, ge=1, le=1000)
    upload_quota_bytes: int = Field(default=1_073_741_824, ge=1)
    upload_image_max_bytes: int = Field(default=15_728_640, ge=1)
    upload_video_max_bytes: int = Field(default=209_715_200, ge=1)
    upload_allowed_user_ids: Annotated[tuple[UUID, ...], NoDecode] = ()
    ffmpeg_binary: str | None = None

    @field_validator("media_allowed_hosts", mode="before")
    @classmethod
    def parse_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(host.strip().lower() for host in value.split(",") if host.strip())
        return value

    @field_validator("upload_allowed_user_ids", mode="before")
    @classmethod
    def parse_upload_allowed_user_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
