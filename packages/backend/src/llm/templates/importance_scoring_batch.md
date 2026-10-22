## Task

Score the importance of each numbered memory for an autonomous agent from 1 to 10.

## Scale

- 1-3: trivial routine
- 4-6: somewhat meaningful
- 7-8: important for goals or relationships
- 9-10: critical

## Context

- Agent: $agent_name
- Identity stable set: $identity_text
- Current plan: $current_plan_text

## Observations

$observations

## Output Contract

Score every observation independently, in the same order. Return strict JSON only with exactly $count integers and no extra text: $json_shape.
