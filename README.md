<div align="center">
  <img src="frontend/assets/icon.png" alt="Rolig app icon" width="160" />

  <h1>Rolig</h1>

  <p><strong>A pure, personalized stream of memes—one swipe at a time.</strong></p>

  <p>
    Rolig is a cross-platform, TikTok-style meme feed for iOS, Android, and the web.
    It combines fluid media playback with AI-assisted analysis, safety filtering,
    and personalized discovery.
  </p>

  <p>
    <a href="https://devpost.com/software/rolig">
      <img src="https://img.shields.io/badge/OpenAI_Build_Week-View_on_Devpost-003E54?style=for-the-badge" alt="View Rolig on Devpost" />
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/iOS-000000?style=flat-square&logo=apple&logoColor=white" alt="iOS" />
    <img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" />
    <img src="https://img.shields.io/badge/Web-4285F4?style=flat-square&logo=googlechrome&logoColor=white" alt="Web" />
  </p>
</div>

## What is Rolig?

Traditional social platforms mix entertainment with comments, messaging, trends,
and endless social noise. Rolig focuses on one thing: delivering a seamless stream
of memes matched to your sense of humor.

- Full-screen vertical paging with clean, TikTok-style snapping
- Image and video playback with proactive three-item media prefetching
- Cursor-based infinite scrolling with loading, empty, and offline states
- AI-assisted tagging, safety analysis, and vector-powered recommendations
- Audited media attribution and a private moderation pipeline
- One shared React Native codebase across iOS, Android, and web

## Built with

### Frontend

![React Native](https://img.shields.io/badge/React_Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Expo](https://img.shields.io/badge/Expo-000020?style=for-the-badge&logo=expo&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![NativeWind](https://img.shields.io/badge/NativeWind-38BDF8?style=for-the-badge&logo=tailwindcss&logoColor=white)

### Backend and data

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Cloudflare R2](https://img.shields.io/badge/Cloudflare_R2-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)

### AI and delivery

![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=000000)

## Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Client | React Native, Expo, TypeScript, NativeWind | Shared iOS, Android, and web experience |
| API | FastAPI, Python | Feed, authentication, uploads, moderation, and AI orchestration |
| Database | Supabase PostgreSQL, pgvector | Meme records, attribution, users, and vector embeddings |
| Media | Cloudflare R2 | Public delivery and private upload quarantine |
| Cache | Redis | Feed caching and upload rate limiting |
| AI | OpenAI | Content understanding, safety analysis, tagging, and embeddings |
| Hosting | Vercel, Render | Web frontend and backend API delivery |

## Repository layout

```text
Rolig/
├── frontend/    # Expo + React Native application
├── backend/     # FastAPI service, tests, migrations, and demo-data tooling
├── SECURITY.md  # Vulnerability reporting and secret-handling policy
└── README.md
```

## Run locally

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env
npm run typecheck
npm run ios       # or: npm run android / npm run web
```

Only `EXPO_PUBLIC_*` client values belong in `frontend/.env`. Never place service
credentials or privileged Supabase keys in the frontend.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
ruff check .
pytest -q
uvicorn app.main:app --reload
```

Apply the SQL files in `backend/migrations/` to Supabase in numeric order. Keep all
database, Redis, R2, and OpenAI credentials in the backend host's encrypted
environment—never in Git.

## Contributing

We welcome focused issues and pull requests.

1. Create a short-lived branch from `pre-release`.
2. Keep frontend work in `frontend/` and backend work in `backend/`.
3. Run the relevant TypeScript, Ruff, and pytest checks.
4. Confirm that no `.env` files, credentials, or media binaries are staged.
5. Open a pull request into `pre-release`; release changes move from
   `pre-release` to `main`.

Please review [SECURITY.md](SECURITY.md) before reporting a vulnerability or
working with deployment configuration.

## OpenAI Build Week contributors

Rolig was designed and built during OpenAI Build Week through a distributed,
cross-time-zone collaboration:

- **Shaun Lin** — cross-platform frontend, mobile engineering, and integration
- **Sunny Yang** — product design, UI/UX, and meme interaction experience
- **Roger Chen** — backend architecture, data infrastructure, and secure media pipeline

Thank you to all three contributors for turning Rolig from an idea into a working
cross-platform experience.

<div align="center">
  <p>
    <strong>Built for OpenAI Build Week.</strong><br />
    <a href="https://devpost.com/software/rolig">View the Rolig submission on Devpost →</a>
  </p>
</div>
