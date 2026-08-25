from dataclasses import dataclass

from agents.planning.react_gate import PlanDisruptionDecision
from agents.reaction import EncounterDecision, ReactionDecision


@dataclass(frozen=True)
class ActionDiagnostics:
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
