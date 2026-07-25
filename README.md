# Rolig

Rolig is a cross-platform, TikTok-style app powered by GPT-5.6 and Codex that lets you endlessly scroll through curated memes, perfectly matching your daily vibe to bring instant joy to your life.

## Mobile feed shell

The Expo + React Native application lives in `frontend/`. It includes a
NativeWind-styled, full-screen vertical meme feed with image/video playback and
a three-item media prefetch window.

```bash
cd frontend
npm install
npm run typecheck
npm run ios      # or: npm run android / npm run web
```

Copy `frontend/.env.example` to `frontend/.env` and set `EXPO_PUBLIC_API_URL`
to the FastAPI deployment before starting the app. This is a public client
value; all privileged credentials must remain in the backend host's encrypted
environment.

## Backend

The FastAPI service lives in `backend/`. Apply the SQL files in `backend/migrations/`
to Supabase in numeric order, copy `backend/.env.example` to `backend/.env`, and fill
in the service credentials.

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

### Approved demo data

The audited demo-data importer validates rights metadata, uploads approved image/video
files to R2, verifies public byte-range delivery, creates idempotent Supabase records,
and invalidates cached feeds. See `backend/demo_data/README.md` and start with a dry run:

```bash
cd backend
python -m app.demo_data demo_data/manifest.json \
  --assets-dir demo_data/assets \
  --dry-run
```

Actual media under `backend/demo_data/assets/` is ignored and must never be pushed.

### Render

Configure the web service with `backend` as its root directory, use
`pip install -r requirements.txt` as the build command, and start it with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The committed `.python-version` keeps production on the tested Python 3.12 runtime.

## Validation

Run `npm run typecheck` in `frontend/` and `ruff check . && pytest -q` in
`backend/` before opening a pull request.
