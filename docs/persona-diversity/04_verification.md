# Persona diversity verification

Verified on 2026-08-26.

## Persona JSON and focused regression

Command:

```text
for persona_file in persona/{Haeun,Jiho,Jungwoo,Minji,Sujin,Taeo}.json; do
  jq empty "$persona_file"
done
UV_CACHE_DIR=/tmp/agent-crossing-uv-cache uv run pytest \
  tests/test_persona_diversity.py \
  tests/test_persona_relationship.py \
  tests/test_encounter_gate.py \
  tests/test_llm_gateway_unit.py
```

Result after the Haeun redesign: 48 passed. All six JSON
files parsed successfully, every MBTI label and romantic preference is visible
to the prompt, and the encounter/reaction boundary guardrails are present. The
known Pydantic compatibility warning under Python 3.14 remains.

## Full backend regression

Command: `UV_CACHE_DIR=/tmp/agent-crossing-uv-cache pnpm test:backend`

Result: 233 passed, 11 skipped, 5 failed. The failures are outside this change:

- one day-plan schema retry expectation,
- two day-plan canonicalization/retry expectations,
- two settings default expectations.

The affected implementation/config files were already modified in the working
tree before this task and were not changed as part of persona diversity work.

## Workspace build

Command: `pnpm -r build`

Result: passed for shared and frontend. Vite retained the existing large-chunk
warning for the main application bundle.

## Runtime note

Persona JSON is loaded when a runtime is constructed. The currently active
saved session retains its persisted persona and memory history; validating the
new behavior live requires a fresh session rather than mutating the running
session in place.
