from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import asyncpg

from app.schemas import FeedWeights, MemeAnalysis, MemeCreateRequest, MemeResponse
from app.upload_schemas import (
    UploadAttribution,
    UploadDatabaseStatus,
    UploadPresignRequest,
)


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in embedding) + "]"


async def get_upload_usage(pool: asyncpg.Pool, uploader_id: UUID) -> int:
    value = await pool.fetchval(
        """
        SELECT COALESCE(sum(declared_size_bytes), 0)::bigint
        FROM upload_sessions
        WHERE uploader_id = $1
          AND status <> 'rejected'
          AND (status <> 'pending_upload' OR expires_at > now())
        """,
        uploader_id,
    )
    return int(value or 0)


async def create_upload_session(
    pool: asyncpg.Pool,
    *,
    upload_id: str,
    uploader_id: UUID,
    object_key: str,
    payload: UploadPresignRequest,
    expires_at: datetime,
    quota_bytes: int,
) -> None:
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
            uploader_id,
        )
        usage = await connection.fetchval(
            """
            SELECT COALESCE(sum(declared_size_bytes), 0)::bigint
            FROM upload_sessions
            WHERE uploader_id = $1
              AND status <> 'rejected'
              AND (status <> 'pending_upload' OR expires_at > now())
            """,
            uploader_id,
        )
        if int(usage or 0) + payload.size_bytes > quota_bytes:
            raise OverflowError("account storage quota exceeded")
        await connection.execute(
            """
            INSERT INTO upload_sessions (
                upload_id, uploader_id, object_key, original_filename, declared_content_type,
                media_type, declared_size_bytes, status, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending_upload', $8)
            """,
            upload_id,
            uploader_id,
            object_key,
            payload.file_name,
            payload.content_type,
            payload.media_type.value,
            payload.size_bytes,
            expires_at,
        )


async def get_upload_session(pool: asyncpg.Pool, upload_id: str) -> dict[str, object] | None:
    row = await pool.fetchrow(
        """
        SELECT upload_id, uploader_id, object_key, original_filename, declared_content_type,
               media_type, declared_size_bytes, actual_size_bytes, status, meme_id, message,
               attribution_creator_name, attribution_source_url, attribution_license,
               attribution_permission_confirmed, expires_at, completed_at
        FROM upload_sessions
        WHERE upload_id = $1
        """,
        upload_id,
    )
    return dict(row) if row else None


async def begin_upload_processing(
    pool: asyncpg.Pool,
    *,
    upload_id: str,
    uploader_id: UUID,
    actual_size_bytes: int,
    attribution: UploadAttribution,
) -> dict[str, object]:
    zero_vector = _vector_literal([0.0] * 1536)
    async with pool.acquire() as connection, connection.transaction():
        row = await connection.fetchrow(
            """
            SELECT upload_id, uploader_id, object_key, media_type, status, meme_id, message
            FROM upload_sessions
            WHERE upload_id = $1
            FOR UPDATE
            """,
            upload_id,
        )
        if row is None:
            raise LookupError("upload not found")
        if row["uploader_id"] != uploader_id:
            raise PermissionError("upload is owned by another user")
        if row["status"] != UploadDatabaseStatus.PENDING_UPLOAD.value:
            existing = dict(row)
            existing["_started"] = False
            return existing

        meme_id = await connection.fetchval(
            """
            INSERT INTO memes (
                creator_id, media_url, media_type, status, tags, summary, humor_style,
                toxicity_score, embedding, analysis_model, embedding_model
            )
            VALUES (
                $1, $2, $3, 'processing', '{}', 'Processing upload', 'pending',
                0, $4::vector, 'pending', 'pending'
            )
            RETURNING id
            """,
            uploader_id,
            f"r2://quarantine/{upload_id}",
            row["media_type"],
            zero_vector,
        )
        updated = await connection.fetchrow(
            """
            UPDATE upload_sessions
            SET status = 'processing',
                meme_id = $2,
                actual_size_bytes = $3,
                attribution_creator_name = $4,
                attribution_source_url = $5,
                attribution_license = $6,
                attribution_permission_confirmed = $7,
                completed_at = now(),
                updated_at = now()
            WHERE upload_id = $1
            RETURNING upload_id, uploader_id, object_key, original_filename,
                      declared_content_type, declared_size_bytes, media_type, status,
                      meme_id, message
            """,
            upload_id,
            meme_id,
            actual_size_bytes,
            attribution.creator_name,
            str(attribution.source_url),
            attribution.license.value,
            attribution.permission_confirmed,
        )
    if updated is None:
        raise RuntimeError("database did not return the updated upload")
    result = dict(updated)
    result["_started"] = True
    return result


async def reject_upload(
    pool: asyncpg.Pool,
    *,
    upload_id: str,
    message: str,
) -> None:
    async with pool.acquire() as connection, connection.transaction():
        meme_id = await connection.fetchval(
            """
            UPDATE upload_sessions
            SET status = 'rejected', message = $2, updated_at = now()
            WHERE upload_id = $1
            RETURNING meme_id
            """,
            upload_id,
            message,
        )
        if meme_id is not None:
            await connection.execute(
                "UPDATE memes SET status = 'rejected', updated_at = now() WHERE id = $1",
                meme_id,
            )


async def record_sanitized_upload(
    pool: asyncpg.Pool,
    *,
    upload_id: str,
    media_object_key: str,
    analysis_object_key: str,
    content_type: str,
    byte_size: int,
    content_sha256: str,
) -> None:
    await pool.execute(
        """
        UPDATE upload_sessions
        SET sanitized_object_key = $2,
            analysis_object_key = $3,
            sanitized_content_type = $4,
            sanitized_size_bytes = $5,
            sanitized_sha256 = $6,
            message = 'Awaiting moderation',
            updated_at = now()
        WHERE upload_id = $1 AND status = 'processing'
        """,
        upload_id,
        media_object_key,
        analysis_object_key,
        content_type,
        byte_size,
        content_sha256,
    )


async def publish_upload(
    pool: asyncpg.Pool,
    *,
    upload_id: str,
    meme_id: UUID,
    uploader_id: UUID,
    public_url: str,
    analysis_image_url: str | None,
    analysis: MemeAnalysis,
    embedding: Sequence[float],
    analysis_model: str,
    embedding_model: str,
    object_key: str,
    original_filename: str,
    content_sha256: str,
    content_type: str,
    byte_size: int,
    attribution: UploadAttribution,
) -> None:
    permission_basis = {
        "Original content": "original",
        "Permission granted": "direct_permission",
        "Creative Commons": "license",
        "Public domain": "public_domain",
    }[attribution.license.value]
    license_name = attribution.license.value if permission_basis == "license" else None
    license_url = str(attribution.source_url) if permission_basis == "license" else None
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            """
            UPDATE memes
            SET media_url = $2,
                analysis_image_url = $3,
                status = 'ready',
                tags = $4,
                summary = $5,
                humor_style = $6,
                toxicity_score = $7,
                embedding = $8::vector,
                analysis_model = $9,
                embedding_model = $10,
                updated_at = now()
            WHERE id = $1 AND creator_id = $11
            """,
            meme_id,
            public_url,
            analysis_image_url,
            analysis.tags,
            analysis.summary,
            analysis.humor_style,
            analysis.toxicity_score,
            _vector_literal(embedding),
            analysis_model,
            embedding_model,
            uploader_id,
        )
        await connection.execute(
            """
            INSERT INTO meme_asset_rights (
                meme_id, object_key, original_filename, content_sha256, content_type,
                byte_size, attribution_text, source_url, permission_basis, license_name,
                license_url, permission_notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (meme_id) DO NOTHING
            """,
            meme_id,
            object_key,
            original_filename,
            content_sha256,
            content_type,
            byte_size,
            attribution.creator_name,
            str(attribution.source_url),
            permission_basis,
            license_name,
            license_url,
            f"Uploader confirmed: {attribution.license.value}",
        )
        await connection.execute(
            """
            UPDATE upload_sessions
            SET status = 'ready', message = 'Published', updated_at = now()
            WHERE upload_id = $1
            """,
            upload_id,
        )


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
            m.like_count,
            m.view_count,
            m.music_title,
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
