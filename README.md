# Physica Backend

FastAPI backend for the projectile-motion solver, walkthrough generator, visual-scene builder, auth, and failed-question feedback loop.

## Local Run

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
uvicorn core.main:app --host 0.0.0.0 --port 8000
```

The app requires at least one provider key, `GROQ_API_KEY`, `GOOGLE_API_KEY`, or `GEMINI_API_KEY`, before `core.main` can import successfully.

## Beta Checks

```bash
python3 scripts/deployment_gate.py --skip-frontend --skip-visual-benchmark
python3 scripts/regress_feedback_loop_db.py
```

For the full monorepo gate, run `python3 scripts/deployment_gate.py` from the original monorepo before splitting.

## Production

- Set `DATABASE_URL` to the Railway Postgres URL.
- Set `APP_AUTH_SECRET` or `AUTH_SECRET` to a long random value.
- `SESSION_TTL_SECONDS` defaults to `1209600` seconds, which is 14 days.
- Set `GOOGLE_CLIENT_ID` to the OAuth client used by the frontend.
- Set `FRONTEND_ORIGIN` or `FRONTEND_ORIGINS` to the deployed frontend domain.
- Set `FEEDBACK_RETRY_TOKEN` for server-side retry jobs.
- Set `GROQ_API_KEY`, `GOOGLE_API_KEY`, or `GEMINI_API_KEY` for extraction and tutor endpoints.
- Set `PROJECTILE_CLASSIFIER=hybrid` so the LLM chooses from registered projectile engine cases while deterministic extraction remains the fallback.
- Verify `/health` returns `"database": "ok"`.

Successful Google sign-ins are persisted in `users`. App sessions are persisted in `auth_sessions` as hashes only; raw session tokens and Google ID tokens are not stored.
