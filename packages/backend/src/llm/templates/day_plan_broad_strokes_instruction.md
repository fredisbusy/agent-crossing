## Persona Context

- Name: $agent_name (age: $age)
- Innate traits: $innate_traits
- Background: $persona_background

## Yesterday Recap

On $yesterday_date_text, $agent_name did the following:

- $yesterday_summary

## Today Plan Prompt

Today is $today_date_text. Draft $agent_name's structured day plan.

## Fixed Planning Window

- Start: `$planning_window_start`
- End: `$planning_window_end`

## Framing Reference

Framing reference (for style, not output format):

- Name: Eddy Lin (age: 19)
- Innate traits: friendly, outgoing, hospitable
- On Tuesday February 12, Eddy completed his morning routine at 7:00 am and got ready to sleep around 10:00 pm.
- Today is Wednesday February 13. Draft Eddy's structured day plan.

## Requirements

- Return $item_count_requirement plan items in `items`.
- Each item must include all required fields: `start_time`, `end_time`, `location`, `action_content`.
- `start_time` and `end_time` must be ISO 8601 datetime strings with minute precision (`seconds=00`).
- `end_time` must be later than `start_time`.
- Use the same calendar date as `Today is ...`; only the final `end_time` may be midnight on the next date.
- This is a broad-strokes day plan. Use natural human time spans and allow non-hour boundaries like `5:30 pm` when they fit the routine.
- Keep chronological flow from morning to night.
- The first item must start exactly at the fixed planning-window start.
- Every item must start exactly when the previous item ends; gaps and overlaps are invalid.
- The final item must end exactly at the fixed planning-window end.
- Keep `location` behavior-oriented, non-empty, and at most $location_max_chars characters.
- Keep `action_content` to one concise sentence of at most $action_max_chars characters.
- Do not add numbering, bullets, markdown, explanatory text, or additional keys.

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape
