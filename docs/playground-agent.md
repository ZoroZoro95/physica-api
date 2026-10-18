# Playground AI adapter: local review prototype

## Boundary

The adapter exposes four local tools: `create_scene`, `apply_commands`,
`simulate_scene`, `finish_scene`. Arguments use the API's Pydantic command types.
The host retains canonical scene state and calls the separate playground HTTP
API. No generated code, arbitrary formulas, filesystem tools or network tools
are exposed to the model. Physics results come only from the simulation API.

This is a CLI integration, not a public endpoint or student-app feature. It
supports text input and one point particle under gravity against stationary
ground, wedges or stairs. Images, symbolic solving, sliding, interacting bodies,
bounces and narration generation are outside this increment.

## Run

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
Provider timeouts are 30 seconds, HTTP timeouts 15 seconds. Provider retries are
disabled; the loop is capped at 8 model rounds and 16 tool calls, with at most
3000 completion tokens per model round. This is a bounded local prototype, not
a production cost or concurrency policy.

## Outputs

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

Live provider acceptance is pending until a valid Groq key/model is configured.
