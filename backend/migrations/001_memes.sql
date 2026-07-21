CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id uuid NOT NULL,
    media_url text NOT NULL,
    analysis_image_url text,
    media_type text NOT NULL CHECK (media_type IN ('image', 'video')),
    status text NOT NULL CHECK (status IN ('ready', 'rejected')),
    tags text[] NOT NULL DEFAULT '{}',
    summary text NOT NULL,
    humor_style text NOT NULL,
    toxicity_score real NOT NULL CHECK (toxicity_score >= 0 AND toxicity_score <= 1),
    embedding vector(1536) NOT NULL,
    analysis_model text NOT NULL,
    embedding_model text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_meme_interactions (
    user_id uuid NOT NULL,
    meme_id uuid NOT NULL REFERENCES memes(id) ON DELETE CASCADE,
    watch_time_seconds double precision NOT NULL DEFAULT 0 CHECK (watch_time_seconds >= 0),
    liked boolean NOT NULL DEFAULT false,
    skipped boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, meme_id)
);

CREATE INDEX IF NOT EXISTS memes_ready_created_idx
    ON memes (created_at DESC)
    WHERE status = 'ready';

CREATE INDEX IF NOT EXISTS memes_embedding_hnsw_idx
    ON memes USING hnsw (embedding vector_cosine_ops)
    WHERE status = 'ready';

CREATE INDEX IF NOT EXISTS interactions_user_updated_idx
    ON user_meme_interactions (user_id, updated_at DESC);

ALTER TABLE memes ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_meme_interactions ENABLE ROW LEVEL SECURITY;

-- No client policies are created intentionally. The FastAPI backend accesses these
-- tables through its server-side database role; direct anonymous access stays denied.
