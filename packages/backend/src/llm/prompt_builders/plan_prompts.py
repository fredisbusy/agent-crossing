import datetime

from agents.planning.models import DayPlanItem, HourlyPlanItem

from ..template_loader import render_template
from .formatting import format_date_text, format_datetime_text, format_plan_line
from .shapes import (
    DAY_PLAN_JSON_SHAPE,
    HOURLY_PLAN_JSON_SHAPE,
    MINUTE_PLAN_JSON_SHAPE,
)


def build_day_plan_prompt(
    *,
    agent_name: str,
    age: int,
    innate_traits: list[str],
    persona_background: str,
    yesterday_date: datetime.datetime,
    yesterday_summary: str,
    today_date: datetime.datetime,
) -> str:
    """Build a persona-grounded prompt for daily structured plan generation."""
    traits_text = ", ".join(trait.strip() for trait in innate_traits if trait.strip())
    return render_template(
        "day_plan_broad_strokes_instruction.md",
        agent_name=agent_name,
        age=str(age),
        innate_traits=traits_text or "N/A",
        persona_background=persona_background.strip(),
        yesterday_date_text=format_date_text(yesterday_date),
        yesterday_summary=yesterday_summary.strip(),
        today_date_text=format_date_text(today_date),
        json_shape=DAY_PLAN_JSON_SHAPE,
    )


def build_hourly_plan_prompt(
    *,
    agent_name: str,
    current_time: datetime.datetime,
    day_plan_item: DayPlanItem,
) -> str:
    day_plan_lines = format_plan_line(
        start_time=day_plan_item.start_time,
        end_time=day_plan_item.end_time,
        location=day_plan_item.location,
        action_content=day_plan_item.action_content,
    )

    return render_template(
        "hourly_plan_instruction.md",
        agent_name=agent_name,
        current_time=format_datetime_text(current_time),
        planning_date=current_time.date().isoformat(),
        day_plan_lines=day_plan_lines,
        json_shape=HOURLY_PLAN_JSON_SHAPE,
    )


def build_minute_plan_prompt(
    *,
    agent_name: str,
    current_time: datetime.datetime,
    hourly_plan_item: HourlyPlanItem,
) -> str:
    hourly_plan_lines = format_plan_line(
        start_time=hourly_plan_item.start_time,
        end_time=hourly_plan_item.end_time,
        location=hourly_plan_item.location,
        action_content=hourly_plan_item.action_content,
    )

    return render_template(
        "minute_plan_instruction.md",
        agent_name=agent_name,
        current_time=format_datetime_text(current_time),
        planning_date=current_time.date().isoformat(),
        hourly_plan_lines=hourly_plan_lines,
        json_shape=MINUTE_PLAN_JSON_SHAPE,
    )
