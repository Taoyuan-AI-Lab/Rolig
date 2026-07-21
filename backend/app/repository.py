from collections.abc import Sequence
from uuid import UUID

import asyncpg

from app.schemas import FeedWeights, MemeAnalysis, MemeCreateRequest, MemeResponse


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in embedding) + "]"


async def insert_meme(
    pool: asyncpg.Pool,
    *,
    payload: MemeCreateRequest,
    analysis: MemeAnalysis,
    embedding: Sequence[float],
    analysis_model: str,
    embedding_model: str,
) -> MemeResponse:
    status = "ready" if analysis.is_safe else "rejected"
    row = await pool.fetchrow(
        """
        INSERT INTO memes (
            creator_id, media_url, analysis_image_url, media_type, status, tags,
            summary, humor_style, toxicity_score, embedding, analysis_model, embedding_model
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector, $11, $12)
        RETURNING id, creator_id, media_url, media_type, status, tags, summary,
                  humor_style, toxicity_score, created_at
        """,
        payload.creator_id,
        str(payload.media_url),
        str(payload.analysis_image_url) if payload.analysis_image_url else None,
        payload.media_type.value,
        status,
        analysis.tags,
        analysis.summary,
        analysis.humor_style,
        analysis.toxicity_score,
        _vector_literal(embedding),
        analysis_model,
        embedding_model,
    )
    if row is None:
        raise RuntimeError("database did not return the created meme")
    return MemeResponse.model_validate(dict(row))


async def fetch_feed(
    pool: asyncpg.Pool,
    *,
    user_id: UUID,
    weights: FeedWeights,
    limit: int,
    offset: int = 0,
) -> list[dict[str, object]]:
    rows = await pool.fetch(
        """
        WITH signals AS (
            SELECT
                i.meme_id,
                ($2::double precision * i.watch_time_seconds)
                    + ($3::double precision * i.liked::int)
                    - ($4::double precision * i.skipped::int) AS score
            FROM user_meme_interactions AS i
            WHERE i.user_id = $1
        ),
        preference AS (
            SELECT avg(m.embedding) AS embedding
            FROM signals AS s
            JOIN memes AS m ON m.id = s.meme_id
            WHERE s.score > 0 AND m.status = 'ready'
        )
        SELECT
            m.id,
            m.creator_id,
            m.media_url,
            m.media_type,
            m.tags,
            m.summary,
            m.humor_style,
            COALESCE(s.score, 0)::double precision AS score,
            CASE
                WHEN p.embedding IS NULL THEN NULL
                ELSE (1 - (m.embedding <=> p.embedding))::double precision
            END AS similarity,
            m.created_at
        FROM memes AS m
        CROSS JOIN preference AS p
        LEFT JOIN signals AS s ON s.meme_id = m.id
        WHERE m.status = 'ready'
          AND NOT EXISTS (
              SELECT 1
              FROM user_meme_interactions AS skipped
              WHERE skipped.user_id = $1
                AND skipped.meme_id = m.id
                AND skipped.skipped = true
          )
        ORDER BY score DESC, similarity DESC NULLS LAST, m.created_at DESC, m.id
        LIMIT $5 OFFSET $6
        """,
        user_id,
        weights.w1,
        weights.w2,
        weights.w3,
        limit,
        offset,
    )
    return [dict(row) for row in rows]
