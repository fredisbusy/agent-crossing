## Planning Context

- Agent: $agent_name
- Date: $current_time
- Planning date (must stay consistent): $planning_date

## Input Active Day Plan Context

$day_plan_lines

## Task

Decompose the active day-plan block into a chronological hourly plan for the near future.

## Fixed Planning Window

- Start: `$planning_window_start`
- End: `$planning_window_end`

## Requirements

- Return the result in `items`.
- Each item must contain only `start_time`, `end_time`, and `action_content`.
- `start_time` and `end_time` must be ISO 8601 datetime strings with minute precision (`seconds=00`).
- `end_time` must be later than `start_time`.
- Use the same calendar date as `Planning date` unless an item clearly crosses past midnight.
- Keep this plan at hourly granularity. Use hour-scale chunks, but do not force exact clock-hour boundaries when a natural schedule suggests otherwise.
- Keep this broader than a minute plan. Prefer 30-180 minute blocks and do not decompose an activity into 5-15 minute micro-steps.
- Focus on the currently active day-plan item and, if useful, the immediate next transition only.
- Do not restate or regenerate the entire day plan.
- Keep items ordered from earlier to later time.
- The item active at the fixed planning-window start must cover that exact time.
- Every following item must start exactly when the previous item ends; gaps and overlaps are invalid.
- The final item must end exactly at the fixed planning-window end.
- Keep each item aligned with the given active day-plan context.
- Keep each `action_content` to one concise sentence of at most $action_max_chars characters.
- Do not output `location`; the simulation inherits the authoritative location from the active day-plan item.
- Do not add numbering, bullets, markdown, explanatory text, or additional keys.

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape
