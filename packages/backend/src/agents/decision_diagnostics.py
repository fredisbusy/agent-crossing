from dataclasses import dataclass

from agents.planning.react_gate import PlanDisruptionDecision
from agents.reaction import EncounterDecision, ReactionDecision


@dataclass(frozen=True)
class ActionDiagnostics:
    """행동 판단 과정의 요약 사고 텍스트.

    `thought`는 모델의 원시 사고 과정이 아니라, 말풍선/로그에 노출해도 되는
    curated 텍스트다(critique 우선, 없으면 reason으로 폴백). 모델이 실제로
    생성한 원시 사고는 `model_thought`에만 남는다. 두 필드가 동일한 값을
    갖는 것은 버그가 아니라, critique가 존재하는 한 `thought`가 그 값을
    그대로 재사용하도록 설계된 폴백 규칙 때문이다.
    """

    thought: str
    model_thought: str
    self_critique: str
    decision_reason: str
    action_summary: str
    decision_process: dict[str, object]


def build_action_diagnostics(
    *,
    reaction_decision: ReactionDecision,
    speak_decision: bool,
    action_intent: str,
    silent_reason: str,
) -> ActionDiagnostics:
    return ActionDiagnostics(
        thought=(reaction_decision.critique or reaction_decision.reason),
        model_thought=reaction_decision.thought,
        self_critique=reaction_decision.critique,
        decision_reason=reaction_decision.reason,
        action_summary=(
            f"발화 결정={speak_decision}, "
            f"행동 의도={action_intent}, "
            f"반응 여부={reaction_decision.should_react}, "
            f"이유={reaction_decision.reason or '없음'}"
        ),
        decision_process={
            "llm_decision": {
                "should_react": reaction_decision.should_react,
                "reason": reaction_decision.reason,
                "model_thought": reaction_decision.thought,
                "self_critique": reaction_decision.critique,
                "candidate_reaction": reaction_decision.reaction,
            },
            "action": {
                "speak_decision": speak_decision,
                "action_intent": action_intent,
                "silent_reason": silent_reason,
            },
        },
    )


@dataclass(frozen=True)
class PlanDisruptionDiagnostics:
    """§4.3.1 tick-level continue-vs-react judgment log entry."""

    should_react: bool
    reason: str
    decision_process: dict[str, object]


def build_plan_disruption_diagnostics(
    *,
    agent_name: str,
    decision: PlanDisruptionDecision,
) -> PlanDisruptionDiagnostics:
    return PlanDisruptionDiagnostics(
        should_react=decision.should_react,
        reason=decision.reason,
        decision_process={
            "agent": agent_name,
            "should_react": decision.should_react,
            "reason": decision.reason,
            "parse_success": decision.trace.parse_success,
            "parse_error": decision.trace.parse_error,
        },
    )


@dataclass(frozen=True)
class EncounterDiagnostics:
    """§3.4 조우 시 pass-by vs converse 판정 log entry."""

    should_converse: bool
    reason: str
    decision_process: dict[str, object]


def build_encounter_diagnostics(
    *,
    self_name: str,
    other_name: str,
    decision: EncounterDecision,
) -> EncounterDiagnostics:
    return EncounterDiagnostics(
        should_converse=decision.should_converse,
        reason=decision.reason,
        decision_process={
            "self": self_name,
            "other": other_name,
            "should_converse": decision.should_converse,
            "relationship_summary": decision.relationship_summary,
            "context_summary": decision.context_summary,
            "reason": decision.reason,
            "parse_success": decision.trace.parse_success,
            "parse_error": decision.trace.parse_error,
        },
    )
