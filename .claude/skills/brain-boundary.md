---
name: brain-boundary
description: Check whether a change to the agent brain leaks governance/diagnostics concerns into domain objects, per AGENTS.md §9. Use before adding a field to ActionLoopResult or similar Brain output types.
---

# Brain / Governance / Diagnostics boundary check

Applies to `packages/backend/src/agents/brain/` and anything producing or
consuming `ActionLoopResult` (or similar Brain result objects).

## Classify every new/changed field

1. Is it required for a runtime action decision? (e.g. `talk`, `utterance`,
   `speak_decision`, `action_intent`, `silent_reason`) → allowed on the
   domain result object.
2. Is it a parsing/retry/suppression/fallback/threshold trace? (e.g.
   `raw_response`, `parse_error`, retry_count, threshold, suppress_reason)
   → belongs to `packages/backend/src/llm/governance/` or
   `packages/backend/src/llm/guardrails/`, never the Brain object.
3. Is it an observability/explanation string? (e.g. `model_thought`,
   `self_critique`, `decision_process`, `action_summary`) → assemble in a
   separate diagnostics module, not inside Brain logic.
4. Is it a log/output format decision? → belongs to the diagnostics layer;
   Brain and API must not depend on that format.

If a field doesn't clearly fall into (1), it does not belong on the Brain
result object — move it or flag it in review.
