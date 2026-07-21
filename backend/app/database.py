from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=10,
        statement_cache_size=0,
    )
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.openai = None
    if settings.ai_analysis_enabled:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI analysis is enabled")
        app.state.openai = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.db_pool.close()
