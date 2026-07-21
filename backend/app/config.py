from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
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
    openai_analysis_model: str = "gpt-5.6"
    openai_embedding_model: str = "text-embedding-3-small"
    feed_cache_ttl_seconds: int = Field(default=60, ge=5, le=3600)
    media_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ()

    @field_validator("media_allowed_hosts", mode="before")
    @classmethod
    def parse_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(host.strip().lower() for host in value.split(",") if host.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
