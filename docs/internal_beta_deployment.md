# Internal Beta Deployment

This is the deployment checklist for the first real student beta. Do not skip the auth, DB, and failed-question loop; otherwise the beta will produce screenshots but no useful product feedback.

## Current Gate

Run from the monorepo:

```bash
python3 scripts/deployment_gate.py
```

Expected result:

- Solver regressions pass.
- DPP manifest validates.
- Landing video is under 8 MB.
- Frontend production build passes.
- Visual benchmark renders all projectile beats.
- SVG beat contract passes.
- Visual verifier score is at least 4.0.

The optional image batch requires `GROQ_API_KEY`, `GOOGLE_API_KEY`, or `GEMINI_API_KEY`:

```bash
python3 scripts/deployment_gate.py --include-image-batch
```

## Backend: Railway

Use the backend split repo.

Start command:

```bash
uvicorn core.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Required environment:

```bash
ENVIRONMENT=production
FRONTEND_ORIGIN=https://your-frontend-domain.example
GOOGLE_CLIENT_ID=
APP_AUTH_SECRET=
SESSION_TTL_SECONDS=1209600
FEEDBACK_RETRY_TOKEN=
DATABASE_URL=
GROQ_API_KEY=
GOOGLE_API_KEY=
GEMINI_API_KEY=
PROJECTILE_CLASSIFIER=hybrid
```

Acceptance:

- `/health` returns `{"status":"ok","database":"ok","projectile_classifier":"hybrid"}`.
- Successful Google sign-ins create/update `users`.
- App sessions are stored in `auth_sessions` as hashes and expire after `SESSION_TTL_SECONDS`.
- `/auth/logout` revokes the current server-side session.
- Unsigned users can solve, but failed questions are not persisted.
- Signed-in failed solves create DB tickets.
- `/feedback/questions` requires bearer auth.
- `/feedback/retry` works for a signed-in user or with `X-Feedback-Retry-Token`.

## Frontend: Vercel

Use the frontend split repo.

Required environment:

```bash
NEXT_PUBLIC_API_URL=https://your-backend-domain.example
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
```

Acceptance:

- `/` loads without waiting for the landing video.
- Google sign-in stores `physica.auth`.
- A failed signed-in solve shows a retry queue message.
- `/failed-questions` shows open/resolved tickets.
- The retry button can re-check open tickets.

## Repo Split

Create local split repos:

```bash
python3 scripts/export_split_repos.py --out-dir split_repos --init-git
```

This creates:

- `split_repos/frontend`
- `split_repos/backend`

Then add GitHub remotes and push each repo separately.
