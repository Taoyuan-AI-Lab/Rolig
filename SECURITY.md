# Security policy

## Secret handling

- Never commit API keys, access tokens, passwords, private keys, database URLs,
  service-account files, or production environment files.
- Keep Supabase, Cloudflare R2, OpenAI, Render, and Vercel credentials in each
  provider's encrypted environment-variable store.
- Mobile and web bundles are public clients. They may contain only explicitly
  public identifiers; privileged operations and service-role credentials must
  remain in the FastAPI backend.
- Commit placeholder files only as `.env.example` or `.env.template`, with
  empty or clearly fake values.
- Use least-privilege tokens, separate development and production credentials,
  and rotate credentials on team-member or scope changes.

## Before every push

1. Review staged paths with `git diff --cached --name-only`.
2. Review the staged patch with `git diff --cached`.
3. Run the repository's secret scanner when one is available in CI or locally.
4. Confirm generated builds, logs, local databases, and environment files are
   not staged.

## If a secret is exposed

Treat it as compromised even if the commit was quickly removed. Revoke or
rotate it at the provider first, remove it from Git history, then audit access
logs and dependent deployments. Do not paste the exposed value into an issue,
pull request, chat, or incident report.

## Reporting a vulnerability

Do not open a public issue containing exploit details or sensitive data.
Contact the repository owners privately through the GitHub organization and
include only the minimum information needed to reproduce the issue.
