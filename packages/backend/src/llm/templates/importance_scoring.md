## Task

Score memory importance for an autonomous agent from 1 to 10.

## Scale

- 1-3: trivial routine
- 4-6: somewhat meaningful
- 7-8: important for goals or relationships
- 9-10: critical

## Context

- Agent: $agent_name
- Identity stable set: $identity_text
- Current plan: $current_plan_text
- Observation: $observation

Keep `reason` to one concise sentence of at most $reason_max_chars characters.

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape.
