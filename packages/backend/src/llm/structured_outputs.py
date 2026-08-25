from functools import lru_cache
from typing import Annotated, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model
from planning_locations import CanonicalLocation


DAY_ACTION_MAX_CHARS = 50
DAY_LOCATION_MAX_CHARS = 120
HOURLY_ACTION_MAX_CHARS = 50
MINUTE_ACTION_MAX_CHARS = 30
QUESTION_MAX_CHARS = 60
INSIGHT_MAX_CHARS = 120
IMPORTANCE_REASON_MAX_CHARS = 60
REACTION_UTTERANCE_MAX_CHARS = 120
REACTION_REASON_MAX_CHARS = 120
REACTION_THOUGHT_MAX_CHARS = 160
REACTION_CRITIQUE_MAX_CHARS = 160


DayActionText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=DAY_ACTION_MAX_CHARS
    ),
]
HourlyActionText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=HOURLY_ACTION_MAX_CHARS
    ),
]
MinuteActionText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MINUTE_ACTION_MAX_CHARS
    ),
]
QuestionText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=QUESTION_MAX_CHARS
    ),
]
InsightText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=INSIGHT_MAX_CHARS
    ),
]
ImportanceReasonText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=IMPORTANCE_REASON_MAX_CHARS
    ),
]
ReactionUtteranceText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=REACTION_UTTERANCE_MAX_CHARS,
    ),
]
ReactionReasonText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=REACTION_REASON_MAX_CHARS
    ),
]
ReactionThoughtText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=REACTION_THOUGHT_MAX_CHARS
    ),
]
ReactionCritiqueText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=REACTION_CRITIQUE_MAX_CHARS
    ),
]


class StrictStructuredOutput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class DayPlanOutputItem(StrictStructuredOutput):
    start_time: str = Field(min_length=16, max_length=35)
    end_time: str = Field(min_length=16, max_length=35)
    location: CanonicalLocation
    action_content: DayActionText


class DayPlanOutput(StrictStructuredOutput):
    items: list[DayPlanOutputItem] = Field(min_length=5, max_length=8)


class DayPlanDraftOutput(StrictStructuredOutput):
    """Bounded provider draft; semantic parsing compacts it to 5-8 strokes."""

    items: list[DayPlanOutputItem] = Field(min_length=5, max_length=16)


@lru_cache(maxsize=8)
def day_plan_output_model(
    *, min_items: int, max_items: int
) -> type[BaseModel]:
    if not 1 <= min_items <= max_items <= 8:
        raise ValueError("day-plan schema bounds must satisfy 1 <= min <= max <= 8")
    if min_items == 5 and max_items == 8:
        return DayPlanOutput
    return create_model(
        f"DayPlanOutput{min_items}To{max_items}",
        __base__=StrictStructuredOutput,
        items=(
            list[DayPlanOutputItem],
            Field(min_length=min_items, max_length=max_items),
        ),
    )


class HourlyPlanOutputItem(StrictStructuredOutput):
    start_time: str = Field(min_length=16, max_length=35)
    end_time: str = Field(min_length=16, max_length=35)
    action_content: HourlyActionText


class HourlyPlanOutput(StrictStructuredOutput):
    items: list[HourlyPlanOutputItem] = Field(min_length=1, max_length=24)


class MinutePlanOutputItem(StrictStructuredOutput):
    duration_minutes: Literal[5, 10, 15]
    action_content: MinuteActionText


class MinutePlanOutput(StrictStructuredOutput):
    items: list[MinutePlanOutputItem] = Field(min_length=1, max_length=36)


class SalientQuestionsOutput(StrictStructuredOutput):
    questions: list[QuestionText] = Field(min_length=3, max_length=3)


class InsightOutputItem(StrictStructuredOutput):
    insight: InsightText
    citation_statement_numbers: list[int] = Field(min_length=1, max_length=10)


class InsightsOutput(StrictStructuredOutput):
    insights: list[InsightOutputItem] = Field(min_length=5, max_length=5)


class ImportanceOutput(StrictStructuredOutput):
    importance: int = Field(ge=1, le=10)
    reason: ImportanceReasonText


class ReactionIntentOutput(StrictStructuredOutput):
    should_react: bool
    thought: ReactionThoughtText
    critique: ReactionCritiqueText
    reason: ReactionReasonText
    end_dialogue: bool


class ReactionUtteranceOutput(StrictStructuredOutput):
    utterance: ReactionUtteranceText
    thought: ReactionThoughtText
    critique: ReactionCritiqueText
    reason: ReactionReasonText
    end_dialogue: bool


__all__ = [
    "DAY_ACTION_MAX_CHARS",
    "DAY_LOCATION_MAX_CHARS",
    "DayPlanOutput",
    "HOURLY_ACTION_MAX_CHARS",
    "HourlyPlanOutput",
    "IMPORTANCE_REASON_MAX_CHARS",
    "INSIGHT_MAX_CHARS",
    "ImportanceOutput",
    "InsightsOutput",
    "MINUTE_ACTION_MAX_CHARS",
    "MinutePlanOutput",
    "QUESTION_MAX_CHARS",
    "REACTION_CRITIQUE_MAX_CHARS",
    "REACTION_REASON_MAX_CHARS",
    "REACTION_THOUGHT_MAX_CHARS",
    "REACTION_UTTERANCE_MAX_CHARS",
    "ReactionIntentOutput",
    "ReactionUtteranceOutput",
    "SalientQuestionsOutput",
]
