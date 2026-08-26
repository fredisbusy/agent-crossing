from functools import lru_cache
from typing import Annotated, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model
from planning_locations import CanonicalLocation
from planning_constraints import DAY_PLAN_MAX_DURATION_MINUTES


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
    """Canonical broad-strokes plan after provider-draft normalization."""

    items: list[DayPlanOutputItem] = Field(min_length=5, max_length=8)


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


PLAN_DISRUPTION_REASON_MAX_CHARS = 120
ENCOUNTER_REASON_MAX_CHARS = 160

PlanDisruptionReasonText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PLAN_DISRUPTION_REASON_MAX_CHARS,
    ),
]
EncounterReasonText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=ENCOUNTER_REASON_MAX_CHARS,
    ),
]


class PlanDisruptionOutput(StrictStructuredOutput):
    """§4.3.1 continue-vs-react judgment: does the observation disrupt the
    agent's current plan enough to warrant reacting?"""

    should_react: bool
    reason: PlanDisruptionReasonText


class EncounterOutput(StrictStructuredOutput):
    """§3.4/§4.3 encounter judgment: pass-by or converse, grounded in a
    relationship summary and a context summary."""

    should_converse: bool
    relationship_summary: EncounterReasonText
    context_summary: EncounterReasonText
    reason: EncounterReasonText


INTERVIEW_REASON_MAX_CHARS = 160

InterviewReasonText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=INTERVIEW_REASON_MAX_CHARS,
    ),
]


class InterviewOutput(StrictStructuredOutput):
    """§7.1 interview judgment: yes/no answer grounded in numbered memory
    statements shown in the prompt, with citation numbers back to them."""

    answer_yes: bool
    citation_statement_numbers: list[int] = Field(min_length=0, max_length=10)
    reason: InterviewReasonText


INTERVIEW_ANSWER_MAX_CHARS = 400

InterviewAnswerText: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=INTERVIEW_ANSWER_MAX_CHARS,
    ),
]


class InterviewAnswerOutput(StrictStructuredOutput):
    """§6.1 25-question interview evaluator: free-text, in-character answer
    grounded in numbered memory statements, with citation numbers back to
    them (empty list is valid when the agent answers from general identity
    rather than a specific memory)."""

    answer: InterviewAnswerText
    citation_statement_numbers: list[int] = Field(min_length=0, max_length=10)


INTERVIEW_SCORE_REASON_MAX_CHARS = 160


class InterviewScoreOutput(StrictStructuredOutput):
    """§6.1/§6.2 absolute scoring of one interview answer (1=incoherent or
    ungrounded, 5=specific, consistent, and well-grounded in memory)."""

    score: Annotated[int, Field(ge=1, le=5)]
    reasoning: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=INTERVIEW_SCORE_REASON_MAX_CHARS,
        ),
    ]


__all__ = [
    "DAY_ACTION_MAX_CHARS",
    "DAY_LOCATION_MAX_CHARS",
    "DAY_PLAN_MAX_DURATION_MINUTES",
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
    "ENCOUNTER_REASON_MAX_CHARS",
    "EncounterOutput",
    "PLAN_DISRUPTION_REASON_MAX_CHARS",
    "PlanDisruptionOutput",
    "INTERVIEW_REASON_MAX_CHARS",
    "InterviewOutput",
    "INTERVIEW_ANSWER_MAX_CHARS",
    "InterviewAnswerOutput",
    "INTERVIEW_SCORE_REASON_MAX_CHARS",
    "InterviewScoreOutput",
]
