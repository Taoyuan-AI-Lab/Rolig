# Rolig
Rolig is a cross-platform, TikTok-style app powered by GPT-5.6 and Codex that lets you endlessly scroll through curated memes, perfectly matching your daily vibe to bring instant joy to your life.

## Backend

The FastAPI service lives in `backend/`. Apply `backend/migrations/001_memes.sql` in
Supabase, copy `backend/.env.example` to `backend/.env`, and fill in the service credentials.

Run locally:

```bash
cd backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Primary routes:

- `POST /api/v1/memes` analyzes and stores an image meme. Video memes include an
  `analysis_image_url` containing a representative frame.
- `GET /api/v1/memes/feed/{user_id}` ranks safe memes and caches the JSON item array in Redis.
- `GET /api/v1/feed?cursor=<cursor>&limit=20` returns the mobile/web client contract with
  opaque pagination and a normalized score between 0 and 1.

Set `AI_ANALYSIS_ENABLED=false` to run the feed without an OpenAI API key. In that mode,
`POST /api/v1/memes` returns `503` because new uploads cannot be analyzed or embedded.
