## Planning Context

- Agent: $agent_name
- Current time: $current_time
- Planning date (must stay consistent): $planning_date

## Input Active Hourly Plan Context

$hourly_plan_lines

## Task

Decompose the active hourly task into concrete subtasks with durations.

## Fixed Planning Window

- Start: `$planning_window_start`
- End: `$planning_window_end`
- Total duration: `$total_duration_minutes` minutes
- Canonical location supplied by the simulation: `$canonical_location`

## Requirements

- Return the result in `items`.
- Each item must contain only `duration_minutes` and `action_content`.
- `duration_minutes` must be exactly `5`, `10`, or `15`.
- Aim for a total of exactly `$total_duration_minutes`; the simulation will fit only the final boundary if the arithmetic differs.
- Do not output `start_time`, `end_time`, or `location`; the simulation owns those authoritative fields.
- Keep items ordered from earlier to later time.
- Keep the sequence chronological and cover the requested activity with concrete steps.
- Prefer 10-15 minute items; use 5 minutes only when the action genuinely needs a short boundary.
- Keep each `action_content` to one concise sentence of at most $action_max_chars characters.
- Do not simply copy hourly-plan summaries or emit one item per hourly block.
- Focus on concrete actions that can be executed immediately.
- Do not add numbering, bullets, markdown, explanatory text, or additional keys.

Example for a 20-minute window:
`{"items":[{"duration_minutes":10,"action_content":"첫 번째 구체적 행동"},{"duration_minutes":5,"action_content":"다음 구체적 행동"},{"duration_minutes":5,"action_content":"마무리 행동"}]}`

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape
