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

Copy `frontend/.env.example` to `frontend/.env` and set `EXPO_PUBLIC_API_URL`,
`EXPO_PUBLIC_SUPABASE_URL`, and `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` before
starting the app. These are public client values. Never place a Supabase secret
or service-role key, JWT signing secret, R2 credential, or OpenAI key in the
frontend environment.

The feed includes a cross-platform upload modal for permitted meme media. Its
presigned upload flow and backend security requirements are documented in
[`frontend/UPLOAD_API_CONTRACT.md`](frontend/UPLOAD_API_CONTRACT.md). The client
never stores R2 credentials and does not call the existing meme creation route
until the backend has verified the uploaded object.

The account sheet supports Supabase email/password sign-in and registration.
Native refresh sessions are encrypted with iOS Keychain or Android Keystore-backed
SecureStore; web sessions use browser storage. Short-lived user access tokens are
sent only as `Authorization: Bearer` headers to protected backend calls. To enable
demo uploads, add the signed-in user's Supabase UUID to Render's
`UPLOAD_ALLOWED_USER_IDS`.

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
- `POST /api/v1/uploads/presign` creates an authenticated, five-minute R2 PUT URL.
- `POST /api/v1/uploads/{upload_id}/complete` verifies and quarantines uploaded media.
- `GET /api/v1/uploads/{upload_id}` returns uploader-scoped moderation status.

Set `AI_ANALYSIS_ENABLED=false` to run the feed without an OpenAI API key. In that mode,
`POST /api/v1/memes` returns `503`, while secure uploads are sanitized and remain private
with `processing` status until moderation is enabled. Unreviewed media is never published.

### Secure upload deployment

Apply `backend/migrations/003_secure_upload_pipeline.sql`, then create a private R2 bucket
such as `rolig-media-quarantine`. Keep the existing `rolig-media` bucket as the public,
moderation-approved destination. Set `R2_QUARANTINE_BUCKET_NAME` to the private bucket and
do not enable its `r2.dev` URL or attach a public custom domain.

The quarantine bucket CORS policy should allow `PUT` from the deployed Rolig origins with
the `Content-Type` header. Add a lifecycle rule that deletes abandoned quarantine objects.
The public bucket needs only cross-origin `GET`/`HEAD` for media playback.

Upload routes accept a signed Supabase JWT from either `Authorization: Bearer <token>` or
the HTTP-only cookie named by `AUTH_COOKIE_NAME`. They derive creator ownership from the
verified JWT `sub`; client creator IDs and object keys are rejected. Configure the
public `SUPABASE_URL`, the R2 variables in `backend/.env.example`, and the upload
rate/quota limits in Render. The backend verifies ES256 access tokens against
Supabase's cached public JWKS and never needs the legacy JWT signing secret. Set
`UPLOAD_ALLOWED_USER_IDS` to a comma-separated list of authenticated Supabase user
UUIDs permitted to use the demo upload flow; an empty list disables uploads. The
managed `imageio-ffmpeg` dependency supplies the video transcoder unless
`FFMPEG_BINARY` explicitly overrides it.

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

## Landing page

The Next.js and Tailwind marketing site lives in `landing/`.

```bash
cd landing
pnpm install
pnpm dev
```

For Vercel, import this repository as a separate project and set the root
directory to `landing`. Use the Next.js framework preset and `pre-release` as
the production branch initially; switch the production branch to `main` when
the landing page is ready for general release.

## Validation

Run `npm run typecheck` in `frontend/`, `ruff check . && pytest -q` in
`backend/`, and `pnpm build` in `landing/` before opening a pull request.
