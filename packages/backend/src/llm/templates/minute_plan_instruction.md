## Planning Context

- Agent: $agent_name
- Current time: $current_time
- Planning date (must stay consistent): $planning_date

## Input Active Hourly Plan Context

$hourly_plan_lines

## Task

Generate an executable minute plan for the current phase.

## Requirements

- Return the result in `items`.
- Each item must include all required fields: `start_time`, `end_time`, `location`, `action_content`.
- `start_time` and `end_time` must be ISO 8601 datetime strings with minute precision (`seconds=00`).
- `end_time` must be 5 to 15 minutes later than `start_time`.
- Use the same calendar date as `Planning date` unless a provided hourly item clearly crosses past midnight.
- This plan may use minute-level start times, but do not include seconds or sub-minute precision.
- Keep items ordered from earlier to later time.
- Focus on the active hourly block and the immediate next transition, not the entire day.
- Break the near-term activity into consecutive concrete 5-15 minute actions for roughly the next 60-90 minutes.
- Do not simply copy hourly-plan summaries or emit one item per hourly block.
- Focus on concrete actions that can be executed immediately.
- Copy the complete `location` value from the active hourly-plan context exactly. Do not shorten, translate, or generalize the location path.
- Do not add numbering, bullets, markdown, explanatory text, or additional keys.

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape
