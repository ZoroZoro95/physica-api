# Deployment Checklist

Purpose: this is the release gate for deploying the projectile-motion product. Do not treat this as a roadmap. A deployment candidate either passes these gates or it does not ship beyond internal beta.

Fast local gate:

```bash
python3 scripts/deployment_gate.py
```

Provider-backed image gate:

```bash
python3 scripts/deployment_gate.py --include-image-batch
```

## Release Mode

- [ ] Internal beta: allowed if solver, extraction, auth, feedback, and build gates pass, even if explainer quality is still being refined.
- [ ] Public product launch: allowed only when explainer and animation sync gates pass on the full acceptance set.

## Gate 1: Repo Hygiene

- [ ] `git status --short` reviewed.
- [ ] Debug reports, generated walkthrough sync reviews, transcripts, local screenshots, and temporary procurement outputs are ignored or intentionally committed.
- [ ] Large media files are intentional. Landing video should live in `frontend/public/landing-simulation.mp4` or an external CDN, not as an accidental duplicate at repo root.
- [ ] No localhost-only URLs are hardcoded in committed production paths.
- [ ] Deployment branch has a clean, understandable commit history.

Commands:

```bash
git status --short
git diff --stat
rg -n "localhost|127.0.0.1|TODO|FIXME" core frontend docs scripts
```

## Gate 2: Backend Solver Coverage

- [ ] Projectile ad-hoc regression suite passes.
- [ ] Equation-plan regression suite passes.
- [ ] DPP manifest validation passes.
- [ ] No solver reads from answer keys or pre-known DPP answers to produce solutions.
- [ ] MCQ matching is only used after computing the answer.
- [ ] Multi-quantity questions return all requested quantities, not only the first detected one.
- [ ] Unsupported questions create feedback tickets instead of failing silently.

Commands:

```bash
python3 scripts/regress_ad_hoc_projectile.py
python3 scripts/regress_projectile_equation_plans.py
python3 scripts/validate_projectile_manifest.py
```

## Gate 3: Image Extraction Coverage

- [ ] The fixed image acceptance set extracts without schema errors.
- [ ] VLM entity-kind aliases normalize safely: `launch_point`, `impact_point`, `target_point`, `inclined_plane`, `initial_velocity`.
- [ ] Extracted options preserve exact exam form, including fractions and square roots.
- [ ] Diagram semantics are present for incline, two-incline, staircase, target, wall, and 3D incline cases.
- [ ] If diagram semantics are incomplete, the app asks for review instead of pretending to solve confidently.

Required batch:

```bash
python3 scripts/review_walkthrough_sync_batch.py \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.11 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.18 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.24 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.30 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.36 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 9.44.42 PM.png" \
  "/Users/siddharth/Desktop/Screenshot 2026-05-25 at 12.41.58 PM.png"
```

Acceptance:

- [ ] All seven images: extraction `ok`.
- [ ] All seven images: solver `passed`.
- [ ] Any hard fail is only `beat-animation sync issues`, not extraction or solver failure.

## Gate 4: Animation Scene Spec

- [ ] Animation scene spec regression passes.
- [ ] Walkthrough sync audit regression passes.
- [ ] `/audit/walkthrough-sync` returns beat pairings plus render probe selectors for every solved explainer beat.
- [ ] Full animation is separate from step replay.
- [ ] Static explanation beats do not play the full trajectory.
- [ ] Step replay replays only the current beat.
- [ ] Incline questions show incline geometry with correct orientation.
- [ ] Staircase question shows collision on the correct step.
- [ ] Component beats show readable vectors and labels.
- [ ] `g sin(alpha)`, `g cos(alpha)`, `v_t`, `v_n`, range, height, launch point, impact point, and collision point can all be highlighted when relevant.

Command:

```bash
python3 scripts/regress_animation_scene_spec.py
python3 scripts/regress_walkthrough_sync_audit.py
node scripts/render_walkthrough_sync_audit.mjs \
  --api http://127.0.0.1:8000 \
  --frontend http://127.0.0.1:3000 \
  --screenshot-dir questions/walkthrough_sync_render_audits/latest
```

Manual checks:

- [ ] Browser/render audit verifies `data-audit-surface="teaching-board-2d"` for every beat, expected vector elements, expected highlighted points/surfaces, and `data-audit-surface="animation-scene-3d"` for full lifecycle.
- [ ] Browser/render audit screenshots are reviewed when selector checks pass but the visual still looks wrong.
- [ ] Perpendicular launch on incline: range along incline is highlighted.
- [ ] Incline collision P/Q: along-plane and normal-axis beats show the right components.
- [ ] Two-incline impact: OA/OB orientation matches the source diagram.
- [ ] Staircase collision: projectile intersects the staircase, not empty space.

## Gate 5: Explainer Quality

This is not currently good enough for public launch. It is acceptable for internal beta only if clearly marked experimental.

- [ ] Each explainer has 5-6 meaningful beats unless the problem genuinely needs more.
- [ ] No duplicated `Breakdown` and `Board` equation blocks.
- [ ] Given rows are deduped, e.g. `t=4s` and `time=4s` do not both display.
- [ ] Language sounds like a teacher, not like a template.
- [ ] Each beat has one clear idea, one visual focus, and only the equations needed for that idea.
- [ ] Formula derivations show the parent equation before substitution when useful.
- [ ] The animation visual plan is generated from the same beat contract the student sees.
- [ ] The current acceptance image batch has no walkthrough score below the agreed threshold.

Current honest status:

- Solver coverage is ahead of explainer quality.
- Animation sync is the main product blocker.
- Do not market this as Khan Academy / Doubtnut-level until this gate passes.

## Gate 6: Frontend Build And UX

- [ ] TypeScript build passes.
- [ ] Landing page loads with the intended video asset.
- [ ] Landing media is beta-sized: `frontend/public/landing-simulation.mp4` is 8 MB or smaller, or the video is hosted externally with a fast poster/fallback.
- [ ] Landing video does not block first paint; it must lazy-load or be external/CDN-backed.
- [ ] Image upload, text input, extraction review, solve, and generate result flows work.
- [ ] MCQ answer display preserves exact option text when options exist.
- [ ] Left and right simulation panels resize/collapse without cutting the animation canvas.
- [ ] First-user simulation guide runs once and can be reopened.
- [ ] Sign-in state does not show sign-in and sign-out side by side.
- [ ] `/failed-questions` loads for signed-in users and shows open/resolved feedback tickets.
- [ ] `/failed-questions` can trigger a retry check for the signed-in user's open questions.

Command:

```bash
cd frontend && npx tsc --noEmit --pretty false
python3 scripts/check_landing_media.py
```

Browser checks:

- [ ] `/` landing page.
- [ ] Text question solve.
- [ ] Image question extraction and review.
- [ ] Explainer mode.
- [ ] Complete solution mode.
- [ ] Full animation mode.
- [ ] Feedback notification path after a failed solve.

## Gate 7: Auth, DB, And Feedback Loop

- [ ] Google OAuth client configured for local and production domains.
- [ ] Backend JWT/auth secret configured.
- [ ] `SESSION_TTL_SECONDS` is explicitly accepted; default is 14 days.
- [ ] Feedback secret configured.
- [ ] Railway database created and migrated/initialized.
- [ ] `DATABASE_URL` is set in production; local development may use the default SQLite DB under `db/app.sqlite`.
- [ ] `/health` reports `"database": "ok"`.
- [ ] A successful `/auth/google` login creates or updates a row in `users`.
- [ ] App sessions are stored in `auth_sessions` as token hashes, not raw tokens.
- [ ] `/auth/me` rejects revoked or expired sessions.
- [ ] `/auth/logout` revokes the current server-side session.
- [ ] Failed question creates a feedback ticket.
- [ ] Feedback tickets persist in the DB, not JSONL files.
- [ ] Retry job can process failed questions.
- [ ] User sees a notification when a previously failed question starts passing.
- [ ] User can open `/failed-questions` to see whether failed questions are still open or resolved.
- [ ] Feedback API is protected; public users cannot mutate other users' tickets.

Command:

```bash
python3 scripts/regress_auth_db.py
python3 scripts/regress_feedback_loop_db.py
```

Required env vars:

```bash
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
APP_AUTH_SECRET=
AUTH_SECRET=
SESSION_TTL_SECONDS=
FEEDBACK_RETRY_TOKEN=
FEEDBACK_SECRET=
DATABASE_URL=
GROQ_API_KEY=
GEMINI_API_KEY=
FRONTEND_ORIGIN=
FRONTEND_ORIGINS=
ENVIRONMENT=production
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
```

## Gate 8: Railway Backend

- [ ] Railway service uses the correct backend start command.
- [ ] Backend health endpoint works.
- [ ] CORS allows only the Vercel production domain and local dev origins.
- [ ] API can reach Groq/Gemini from Railway.
- [ ] API can reach the production database.
- [ ] Logs do not leak auth tokens, API keys, or full private user data.

Smoke checks:

```bash
curl "$RAILWAY_API_URL/health"
curl "$RAILWAY_API_URL/templates/projectile"
```

## Gate 9: Vercel Frontend

- [ ] `NEXT_PUBLIC_API_URL` points to Railway backend.
- [ ] `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is configured.
- [ ] Frontend build succeeds on Vercel.
- [ ] Landing video size is acceptable for page load.
- [ ] Browser console has no auth, CORS, hydration, or asset errors.
- [ ] Vercel domain is added to Google OAuth authorized origins.

## Gate 10: Final Acceptance Set

Minimum pre-deploy acceptance set:

- [ ] Seven uploaded diagram images.
- [ ] All projectile DPP manifest entries.
- [ ] 15 text-only projectile questions.
- [ ] 10 diagram-heavy projectile questions.
- [ ] 5 unsupported or ambiguous questions that must route to review/feedback.

For each passing question, record:

- [ ] Extracted question text.
- [ ] Extracted givens.
- [ ] Requested quantity.
- [ ] Engine case.
- [ ] Computed answer.
- [ ] Matched option, if any.
- [ ] Animation scene spec status.
- [ ] Explainer sync status.

## Ship Decision

Internal beta can ship when:

- [ ] Gates 1, 2, 3, 4, 6, 7, 8, and 9 pass.
- [ ] Gate 5 is explicitly marked experimental in the product.

Public launch can ship when:

- [ ] All gates pass.
- [ ] Explainer/animation sync is good enough that a student can understand the solution without reading a separate static solution.
