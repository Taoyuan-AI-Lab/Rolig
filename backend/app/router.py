import hashlib
import json
import logging
from uuid import UUID

import openai
from fastapi import APIRouter, HTTPException, Query, status
from redis.exceptions import RedisError

from app.dependencies import DatabaseDep, OpenAIDep, RedisDep, SettingsDep
from app.repository import fetch_feed, insert_meme
from app.schemas import (
    ClientFeedItem,
    ClientFeedResponse,
    FeedItem,
    FeedResponse,
    FeedWeights,
    MemeCreateRequest,
    MemeResponse,
)
from app.services import (
    analyze_meme,
    create_embedding,
    decode_feed_cursor,
    encode_feed_cursor,
    normalize_feed_score,
    validate_media_host,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memes", tags=["memes"])
feed_router = APIRouter(tags=["feed"])


@router.post("", response_model=MemeResponse, status_code=status.HTTP_201_CREATED)
async def create_meme(
    payload: MemeCreateRequest,
    db: DatabaseDep,
    openai_client: OpenAIDep,
    settings: SettingsDep,
) -> MemeResponse:
    if not settings.ai_analysis_enabled or openai_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI meme analysis is disabled",
        )
    try:
        await validate_media_host(payload.visual_url, settings.media_allowed_hosts)
        analysis = await analyze_meme(
            openai_client,
            model=settings.openai_analysis_model,
            image_url=payload.visual_url,
        )
        embedding = await create_embedding(
            openai_client,
            model=settings.openai_embedding_model,
            analysis=analysis,
        )
        return await insert_meme(
            db,
            payload=payload,
            analysis=analysis,
            embedding=embedding,
            analysis_model=settings.openai_analysis_model,
            embedding_model=settings.openai_embedding_model,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except openai.APIError as exc:
        logger.exception("OpenAI analysis failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="meme analysis is temporarily unavailable",
        ) from exc


@router.get("/feed/{user_id}", response_model=FeedResponse)
async def get_feed(
    user_id: UUID,
    db: DatabaseDep,
    redis: RedisDep,
    settings: SettingsDep,
    limit: int = Query(default=20, ge=1, le=100),
    w1: float = Query(default=1.0, ge=0, le=100),
    w2: float = Query(default=10.0, ge=0, le=100),
    w3: float = Query(default=15.0, ge=0, le=100),
) -> FeedResponse:
    weights = FeedWeights(w1=w1, w2=w2, w3=w3)
    cache_identity = f"{user_id}:{limit}:{w1:g}:{w2:g}:{w3:g}"
    cache_key = f"rolig:feed:v1:{hashlib.sha256(cache_identity.encode()).hexdigest()}"

    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            items = [FeedItem.model_validate(item) for item in json.loads(cached)]
            return FeedResponse(user_id=user_id, items=items, cache_hit=True)
    except (RedisError, json.JSONDecodeError, ValueError):
        logger.warning("Feed cache read failed", exc_info=True)

    rows = await fetch_feed(db, user_id=user_id, weights=weights, limit=limit)
    items = [FeedItem.model_validate(row) for row in rows]
    serialized = json.dumps([item.model_dump(mode="json") for item in items], separators=(",", ":"))
    try:
        await redis.setex(cache_key, settings.feed_cache_ttl_seconds, serialized)
    except RedisError:
        logger.warning("Feed cache write failed", exc_info=True)
    return FeedResponse(user_id=user_id, items=items, cache_hit=False)


@feed_router.get("/feed", response_model=ClientFeedResponse)
async def get_client_feed(
    db: DatabaseDep,
    redis: RedisDep,
    settings: SettingsDep,
    cursor: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: UUID | None = None,
) -> ClientFeedResponse:
    try:
        offset = decode_feed_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    effective_user_id = user_id or UUID(int=0)
    weights = FeedWeights()
    cache_identity = f"client:{effective_user_id}:{offset}:{limit}"
    cache_key = f"rolig:feed:v2:{hashlib.sha256(cache_identity.encode()).hexdigest()}"

    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            cached_items = [ClientFeedItem.model_validate(item) for item in json.loads(cached)]
            next_cursor = encode_feed_cursor(offset + len(cached_items))
            if len(cached_items) < limit:
                next_cursor = None
            return ClientFeedResponse(items=cached_items, next_cursor=next_cursor)
    except (RedisError, json.JSONDecodeError, ValueError):
        logger.warning("Client feed cache read failed", exc_info=True)

    rows = await fetch_feed(
        db,
        user_id=effective_user_id,
        weights=weights,
        limit=limit,
        offset=offset,
    )
    items = [
        ClientFeedItem(
            id=row["id"],
            url=str(row["media_url"]),
            type=row["media_type"],
            tags=row["tags"],
            score=normalize_feed_score(float(row["score"])),
        )
        for row in rows
    ]
    serialized = json.dumps([item.model_dump(mode="json") for item in items], separators=(",", ":"))
    try:
        await redis.setex(cache_key, settings.feed_cache_ttl_seconds, serialized)
    except RedisError:
        logger.warning("Client feed cache write failed", exc_info=True)

    next_cursor = encode_feed_cursor(offset + len(items)) if len(items) == limit else None
    return ClientFeedResponse(items=items, next_cursor=next_cursor)
