# Playground AI adapter: local review prototype

## Boundary

The CLI now uses an atomic recipe: the model calls `build_and_simulate` with
gravity, typed commands, simulation settings and assumptions. The host runs the
existing create/apply/plan/simulate API operations in order, adopting a candidate
only after simulation succeeds. `finish_scene` is restricted to clarification or
unsupported requests in this mode. Review text is host-generated from the engine
status, not an LLM claim. A no-contact result explicitly remains unsolved.

The CLI is capped at three model rounds and three tool calls, including its one
malformed-tool retry. The eight-round workflow described below remains available
for low-level regression compatibility; it is no longer the CLI default.
Successful internal HTTP operations are recorded under `operations` in reports.

The adapter exposes four local tools: `create_scene`, `apply_commands`,
`simulate_scene`, `finish_scene`. Arguments use the API's Pydantic command types.
The host retains canonical scene state and calls the separate playground HTTP
API. No generated code, arbitrary formulas, filesystem tools or network tools
are exposed to the model. Physics results come only from the simulation API.

This is a CLI integration and an opt-in local HTTP endpoint, not a public authenticated service or student-solver feature. It
supports text input and one point particle under gravity against stationary
ground, wedges or stairs. Images, symbolic solving, sliding, interacting bodies,
bounces and narration generation are outside this increment.

## Run

For the local playground question form, start the backend explicitly:

```sh
PLAYGROUND_AI_ENABLED=1 python -m uvicorn core.playground.main:app --env-file .env --host 127.0.0.1 --port 8001
```

`POST /v1/generate` accepts only `{ "question": "..." }`. Configure `GROQ_API_KEY`
and `PLAYGROUND_MODEL` on the server. No keys, model overrides or target URLs are
accepted from the browser. Generation is disabled by default; keep it disabled
on public services until authentication, shared rate limits and cost controls exist.
The local endpoint allows one generation at a time per process and returns 429
when busy. It uses at most three model rounds, 20-second provider timeouts and no
SDK retries. A browser timeout/disconnect does not cancel provider work already
running. This is not a distributed queue or a production-wide concurrency limit.

Responses contain status, reason, assumptions, report ID and, for review
candidates only, the matching scene, geometry and simulation. The viewer consumes
that exact simulation rather than recalculating it over a different horizon.
Detailed traces stay in the local debug-report directory, not the browser response.

Verification on 2026-10-25: six generation-route tests plus the existing suites
pass. Desktop/mobile mocked UI states and one live explicitly continuing staircase
passed (report `f6931446-9091-4d38-a619-9b316602f998`). An earlier live staircase
without a finite count failed the expected-contact check: the model chose ten
finite steps and returned a time limit (report `0bd52201-6e41-4213-a585-da1b85181513`).
The UI accurately displayed no contact; source interpretation remains imperfect.

Start the separate playground API on port 8001. Use the repository's Python
environment with `requirements-dev.txt` installed (HTTP client and tests).
Set `GROQ_API_KEY` and `PLAYGROUND_MODEL` locally, or provide an explicit env file
and model. Do not commit keys or paste them into reports.

```sh
python scripts/playground_agent.py \
  --env-file .env \
  --model openai/gpt-oss-120b \
  --question "A point particle leaves the top of a descending staircase to the right horizontally at 10 m/s. Each step is 1 m wide and 1 m high. Use g=9.8 m/s^2. Build a scene to inspect the first contact."
```

The named model is a configurable example, not a guaranteed account entitlement.
No default model or unrelated-provider key fallback is used. The implementation
follows [Groq local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling).
Provider timeouts are 30 seconds, HTTP timeouts 15 seconds. The SDK permits up to
two retries per model round and respects provider Retry-After headers; exhausted
rate limits are reported separately from invalid configuration. The loop is
capped at 8 model rounds (at most 24 provider attempts) and 16 tool calls, with at most
3000 completion tokens per model round. This is a bounded local prototype, not
a production cost or concurrency policy.

Tool calls are required at the provider boundary. Before scene creation, only
creation and finish/clarification schemas are sent; other tools become available
once a scene exists. A provider `tool_use_failed` rejection receives at most one
additional attempt within the same eight-round budget. Rejected arguments are
never executed. Repeated rejection fails without exporting a scene.

For a simulation time limit, feedback includes the actual finite surfaces and
horizon, rather than treating a missed contact as unsupported physics. Rebuilding
requires resetting the scene; adding an existing particle is not an update.
Extent provenance is still prompt-enforced, not mechanically verified: a model
can still change a physical input incorrectly. Human review remains mandatory.

## Outputs

`simulate_scene` optionally accepts `continuing_staircases: [surface_id, ...]`.
Only use this for continuing geometry, not a stated finite staircase. The host
calls `/v1/simulations/planned`, which sizes repeated steps to cover horizontal
travel during the requested horizon. Only step count and scene revision change;
gravity, launch, coordinates, rise and run remain unchanged. Limits fail explicitly
rather than silently clipping the geometry. The model still needs to choose a
sufficient time horizon; continuation does not guarantee contact by that time.

The report includes the selected continuing IDs, engine-reported extent changes
in its trace, and a host-added assumption even if the model omits it. Classification
of a question as continuing remains subject to human review. This is not a general
proof that the model preserved every source constraint. Ground and wedge extents
are not automatically expanded by this planner.

Each run writes a separate directory under the git-ignored
`questions/debug_reports/playground-agent/`. `report.json` records the input,
configured model, status, declared assumptions and actual tool arguments/results.
It does not contain environment variables or provider exception contents.

- `review`: the current scene has a matching API simulation. `scene.json` can be
  opened using Import scene in the playground viewer. This is NOT a verified
  interpretation of the question and NOT an accepted answer.
- `needs_clarification`: the model requested missing information; no scene export.
- `unsupported`: the model declined unsupported physics; no scene export.
- `failed`: provider/API/malformed-response error or exhausted budget; no scene export.

Review the source question, object placement, launch direction, supplied values
and assumptions before using a generated scene. The viewer re-simulates imported
scenes over its own time horizon. The report retains the original simulation
horizon, so a later viewer contact must not be confused with an earlier time limit.

The prompt instructs the model not to invent missing inputs and to disclose chosen
display extents. These are semantic instructions, not a formal proof of fidelity.
Schema validation cannot catch a valid-but-wrong angle or fabricated number.
Never interpret `review` as "the question has been solved correctly".

## Verification and outstanding gate

```sh
python scripts/regress_playground_agent.py
python scripts/regress_playground_api.py
python scripts/regress_playground_stairs.py
```

The agent regression suite uses SCRIPTED model responses against the real API
routes. It checks orchestration, varied parameters, mirroring, stale results,
failed atomic batches, invalid commands, model/API failures, terminal decisions
and call budgets. It is not a live language-model or image-understanding test.

Before promoting this adapter, run real-model evaluations for numeric level-ground
launch, changed stair dimensions and names, mirrored stairs, inclined launch,
missing launch data, diagram-dependent ambiguity and unsupported bounce/drag.
Inspect each exported scene against its question and compare API measurements to
independent expected results. A model refusal or an HTTP success is not sufficient.

## Live checkpoint: 2026-10-20

The configured Groq key was accepted with `openai/gpt-oss-120b`. Initial runs hit
the account's 8000-token/minute limit mid-loop. Bounded SDK retries were added;
the follow-up proceeded through scene creation, commands and simulation.

Acceptance FAILED for the horizontal staircase question (10 m/s, rise/run 1 m,
g=9.8). The model chose five steps, so the particle left the finite geometry
without contact. It then tried adding a duplicate particle and falsely claimed
stair collisions were unsupported. Its final response was plain text, not the
required finish tool, so no review candidate was exported. The engine's known
21st-tread result requires a staircase extending far enough to contain that event.

Local evidence: `questions/debug_reports/playground-agent/20261020T143151Z-61839a75/report.json`.
This is a scene-planning and recovery failure, not a successful model evaluation.
Next work must address insufficient illustrative extents and tool-error recovery
generically, then repeat the full live evaluation set. Do not hardcode step 21.

The follow-up with required tools and finite-extent diagnostics still failed:
`20261020T144305Z-94e2495b/report.json`. The model exhausted its round budget,
repeated duplicate additions and shifted the launch point instead of extending
the illustrative staircase correctly. No candidate was exported. Prompt changes
alone have not resolved this failure.

The old text23d model `meta-llama/llama-4-scout-17b-16e-instruct` was absent from
the configured account's live Groq model list. `openai/gpt-oss-20b` is being
evaluated explicitly with `--model`, not silently installed as a fallback.
The first comparison failed before any tool executed; later diagnostics identify
provider rejection of model-generated tool calls as a distinct failure category.

### Follow-up: 2026-10-21

The smaller-model comparison also failed acceptance after bounded recovery:
`questions/debug_reports/playground-agent/20261021T074009Z-d985e49e/report.json`.
It recovered from an invalid surface-relative stair launch and one provider tool
rejection, but retained five steps and repeatedly extended only the time horizon.
The eight-round budget ended without a first contact or exported scene. No default
model configuration was changed. Neither model is accepted for autonomous use.

Verification: 23 scripted orchestration tests, 78 general API requests, and 118
staircase API requests pass. These do not establish live-model reliability.
The next acceptance gate needs explicit separation of given constraints from
illustrative extents, and bounded engine-assisted extent planning that cannot
change the former. More prompt wording or a larger retry budget is not evidence
that this problem is fixed.

### Extent-planning checkpoint: 2026-10-24

A deterministic, opt-in continuing-staircase planner now passes five test methods
covering varied dimensions, speeds, origins, direction, finite geometry, limits,
short horizons and idempotence. The agent suite passes 24 tests, including a
four-tool path from a five-step display to an engine-computed 21st-tread contact
without model-led reconstruction. Existing 78 general and 118 staircase request
checks still pass. None of these are live-model acceptance results.

Live acceptance still FAILED in
`questions/debug_reports/playground-agent/20261024T174241Z-8cc14f54/report.json`:
the model attempted review before scene creation and simulation, then produced
provider-rejected tool calls. No scene was exported. The next orchestration gate
is reliable construction and simulation using the new capability, with finite
and continuing scenarios tested separately. No deployment is approved by these tests.

### Atomic builder checkpoint: 2026-10-24

Two live `openai/gpt-oss-120b` cases now produced correct engine-backed scenes
with one model tool call each:

- Original staircase, speed 10 m/s, rise/run 1 m: tread 21 at 2.070196678 s.
  Report: `20261024T180934Z-b500179f/report.json`.
- Mirrored staircase, particle M at (13,27), speed 8 m/s left, rise 1.2 m,
  run 0.9 m: tread 20; supplied position, velocity, dimensions and gravity were
  independently checked. Report: `20261024T181026Z-304a7efc/report.json`.

Reports are under `questions/debug_reports/playground-agent/`. This is a narrow
live checkpoint, not broad language-model acceptance. Finite stairs, missing
inputs, unsupported physics and non-stair scenes still need live evaluation of
this new path. Seven atomic-builder tests, 24 workflow tests, five planner tests,
78 general API requests and 118 staircase API requests pass. No browser visual
verification or deployment was performed for this backend-only change.
