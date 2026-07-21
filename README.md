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
value; all Supabase service-role, Cloudflare R2, and OpenAI credentials must
remain in the backend host's encrypted environment.

Run `npm run typecheck` before opening a pull request.
