# Rolig demo data

Only use media that the team has approved for the demo. Keep the media files in
`backend/demo_data/assets/`; that directory is ignored so copyrighted files are
not pushed to GitHub.

1. Copy `manifest.example.json` to `manifest.json`.
2. Add one manifest entry per approved asset, including its attribution,
   permission basis, source URL, and permission notes.
3. Put the matching files in `backend/demo_data/assets/`.
4. Apply `backend/migrations/002_demo_asset_metadata.sql` in Supabase.
5. Validate locally without contacting R2 or Supabase:

```bash
python -m app.demo_data demo_data/manifest.json \
  --assets-dir demo_data/assets \
  --dry-run
```

6. Ingest the validated assets:

```bash
python -m app.demo_data demo_data/manifest.json \
  --assets-dir demo_data/assets
```

The importer refuses unapproved entries, path traversal, unsupported media,
files larger than 200 MiB, duplicate IDs or object keys, unrecognized file
signatures, missing license metadata, and replacement of an R2 key with
different bytes. It verifies the uploaded object and its public byte-range URL
before writing the Supabase record, then invalidates the derived Redis feeds.

The deterministic local demo embedding is only a bootstrap fallback while AI
analysis is disabled. Its model marker is `rolig-hash-embedding-v1`; production
uploads should replace it with the configured semantic embedding pipeline.
