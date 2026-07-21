from typing import Annotated

import asyncpg
from fastapi import Depends, Request
from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.config import Settings, get_settings


def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_openai(request: Request) -> AsyncOpenAI | None:
    return request.app.state.openai


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[asyncpg.Pool, Depends(get_db_pool)]
RedisDep = Annotated[Redis, Depends(get_redis)]
OpenAIDep = Annotated[AsyncOpenAI | None, Depends(get_openai)]
