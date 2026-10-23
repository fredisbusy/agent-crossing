import datetime

from agents.planning.models import DayPlanItem, HourlyPlanItem
from agents.planning.plan_prompts import (
    build_day_plan_prompt,
    build_hourly_plan_prompt,
    build_minute_plan_prompt,
)


def test_day_plan_prompt_contains_persona_and_json_shape() -> None:
    prompt = build_day_plan_prompt(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background=(
            "Eddy Lin is a student at Oak Hill College studying music theory and composition."
        ),
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary=(
            "woke up and completed the morning routine at 7:00 am, [...] got ready to sleep around 10 pm."
        ),
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert "Name: Eddy Lin (age: 19)" in prompt
    assert "Innate traits: friendly, outgoing, hospitable" in prompt
    assert "Today is Friday February 13 2026" in prompt
    assert "Draft Eddy Lin's structured day plan." in prompt
    assert "Use the same calendar date as `Today is ...`" in prompt
    assert "Framing reference (for style, not output format):" in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"items": [' in prompt
    assert '"start_time": "<ISO-8601 datetime>"' in prompt
    assert '"end_time": "<ISO-8601 datetime later than start_time>"' in prompt


def test_hourly_plan_prompt_contains_context_and_json_shape() -> None:
    prompt = build_hourly_plan_prompt(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 45, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert (
        "Decompose the active day-plan block into a chronological hourly plan for the near future."
        in prompt
    )
    assert "Friday February 13 2026 at 8:45 AM" in prompt
    assert "Planning date (must stay consistent): 2026-02-13" in prompt
    assert "Prefer 30-180 minute blocks" in prompt
    assert "Do not restate or regenerate the entire day plan." in prompt
    assert "Review composition notes and plan" in prompt
    assert "Attend class" not in prompt
    assert "Study alone" not in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert "'items': [" not in prompt
    assert '"items": [' in prompt
    assert '"end_time": "<ISO-8601 datetime later than start_time>"' in prompt


def test_minute_plan_prompt_contains_context_and_json_shape() -> None:
    prompt = build_minute_plan_prompt(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 20, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    assert "Generate an executable minute plan for the current phase." in prompt
    assert "Friday February 13 2026 at 12:20 PM" in prompt
    assert "Planning date (must stay consistent): 2026-02-13" in prompt
    assert "Do not simply copy hourly-plan summaries" in prompt
    assert "Draft project outline" in prompt
    assert "Take lunch break" not in prompt
    assert "Resume focused writing" not in prompt
    assert "end_time" in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"end_time": "<ISO-8601 datetime 5-15 minutes after start_time>"' in prompt
