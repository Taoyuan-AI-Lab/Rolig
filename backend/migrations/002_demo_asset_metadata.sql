ALTER TABLE memes
    ADD COLUMN IF NOT EXISTS like_count bigint NOT NULL DEFAULT 0
        CHECK (like_count >= 0),
    ADD COLUMN IF NOT EXISTS view_count bigint NOT NULL DEFAULT 0
        CHECK (view_count >= 0),
    ADD COLUMN IF NOT EXISTS music_title text;

CREATE TABLE IF NOT EXISTS meme_asset_rights (
    meme_id uuid PRIMARY KEY REFERENCES memes(id) ON DELETE CASCADE,
    object_key text NOT NULL UNIQUE,
    original_filename text NOT NULL,
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    content_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    attribution_text text NOT NULL,
    source_url text NOT NULL,
    permission_basis text NOT NULL CHECK (
        permission_basis IN ('original', 'direct_permission', 'license', 'public_domain')
    ),
    license_name text,
    license_url text,
    permission_notes text NOT NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        permission_basis <> 'license'
        OR (license_name IS NOT NULL AND license_url IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS meme_asset_rights_sha256_idx
    ON meme_asset_rights (content_sha256);

ALTER TABLE meme_asset_rights ENABLE ROW LEVEL SECURITY;

-- No client policy is intentional: rights and provenance records are backend-only.
