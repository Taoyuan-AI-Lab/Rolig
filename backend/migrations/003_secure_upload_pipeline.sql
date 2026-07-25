ALTER TABLE memes
    DROP CONSTRAINT IF EXISTS memes_status_check;

ALTER TABLE memes
    ADD CONSTRAINT memes_status_check
    CHECK (status IN ('processing', 'ready', 'rejected'));

CREATE TABLE IF NOT EXISTS upload_sessions (
    upload_id text PRIMARY KEY CHECK (upload_id ~ '^upl_[A-Za-z0-9_-]{20,64}$'),
    uploader_id uuid NOT NULL,
    object_key text NOT NULL UNIQUE,
    original_filename text NOT NULL,
    declared_content_type text NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('image', 'video')),
    declared_size_bytes bigint NOT NULL CHECK (declared_size_bytes > 0),
    actual_size_bytes bigint CHECK (actual_size_bytes > 0),
    sanitized_object_key text UNIQUE,
    analysis_object_key text UNIQUE,
    sanitized_content_type text,
    sanitized_size_bytes bigint CHECK (sanitized_size_bytes > 0),
    sanitized_sha256 text CHECK (
        sanitized_sha256 IS NULL OR sanitized_sha256 ~ '^[0-9a-f]{64}$'
    ),
    status text NOT NULL CHECK (
        status IN ('pending_upload', 'processing', 'ready', 'rejected')
    ),
    meme_id uuid UNIQUE REFERENCES memes(id) ON DELETE SET NULL,
    message text,
    attribution_creator_name text,
    attribution_source_url text,
    attribution_license text,
    attribution_permission_confirmed boolean,
    expires_at timestamptz NOT NULL,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS upload_sessions_owner_created_idx
    ON upload_sessions (uploader_id, created_at DESC);

CREATE INDEX IF NOT EXISTS upload_sessions_abandoned_idx
    ON upload_sessions (expires_at)
    WHERE status = 'pending_upload';

ALTER TABLE upload_sessions ENABLE ROW LEVEL SECURITY;

-- Direct client access remains denied. The FastAPI server owns this state machine.
