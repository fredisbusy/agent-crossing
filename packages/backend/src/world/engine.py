import datetime
from dataclasses import dataclass, field
from typing import Literal

from agents.brain import ActionLoopInput, ActionLoopResult
from agents.sim_agent import SimAgent
from llm.governance import (
    apply_reply_policy,
    is_reaction_parse_failure,
    merge_policy_trace,
    recent_replies_for_echo_check,
)

from .session import (
    WorldConversationSession,
    build_turn_observed_events,
    build_turn_world_context,
)


@dataclass(frozen=True)
class SimulationStepResult:
    """시뮬레이션 한 턴의 실행 결과."""

    """이번 턴의 시뮬레이션 실행 결과 시각."""
    now: datetime.datetime
    """발화 주체 에이전트 이름."""
    speaker_name: str
    """거버넌스 추적과 정책 병합 정보를 담은 진단 트레이스."""
    trace: dict[str, object]
    """정책 적용 이후 최종 확정된 발화문."""
    reply: str
    """무발화 시점의 억제/침묵 사유."""
    silent_reason: str
    """LLM 반응 파싱 실패 여부."""
    parse_failure: bool
    """관측/로그 출력용 진단 페이로드."""
    observability: "SimulationStepObservability"
    """현재 계획/대화 모드 관련 운영 진단 정보."""
    plan_diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationStepObservability:
    """행동 판단 과정의 요약 사고 텍스트."""

    thought: str
    """모델이 생성한 내부 사고 텍스트."""
    model_thought: str
    """모델 자기 비평 텍스트."""
    self_critique: str
    """최종 의사결정 근거 요약."""
    decision_reason: str
    """이번 턴의 행동 결정 요약 문자열."""
    action_summary: str
    """의사결정 중간 산출물과 정책 결과를 담은 상세 구조."""
    decision_process: dict[str, object]
    """현재 계획/대화 모드 관련 운영 진단 정보."""
    plan_diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationEngineConfig:
    """시뮬레이션 엔진 동작 정책 설정."""

    """시뮬레이션 출력/정책에 사용할 언어."""
    language: Literal["ko", "en"]
    """턴마다 증가시킬 시뮬레이션 시간(초)."""
    turn_time_step_seconds: int
    """최근 발화와 중복된 응답을 억제할지 여부."""
    suppress_repeated_replies: bool
    """중복 판정을 위해 비교할 최근 발화 개수."""
    repetition_window: int
    """최종 응답이 비었을 때 폴백 문장을 주입할지 여부."""
    fallback_on_empty_reply: bool


class SimulationEngine:
    def __init__(
        self,
        *,
        session: WorldConversationSession,
        config: SimulationEngineConfig,
    ):
        self.session: WorldConversationSession = session
        self.config: SimulationEngineConfig = config

    def step(
        self,
        *,
        turn: int,
        current_time: datetime.datetime,
        speaker: SimAgent,
        speaking_partner: SimAgent,
    ) -> SimulationStepResult:
        if not self.session.is_active:
            return self._build_inactive_step_result(
                current_time=current_time,
                speaker=speaker,
            )

        incoming_partner_utterance = self.session.consume_incoming_partner_utterance(
            speaker=speaker
        )
        now = current_time + datetime.timedelta(
            seconds=self.config.turn_time_step_seconds
        )
        action_result = self._run_action_loop(
            turn=turn,
            now=now,
            speaker=speaker,
            speaking_partner=speaking_partner,
            incoming_partner_utterance=incoming_partner_utterance,
        )
        raw_reply = (action_result.utterance or action_result.talk or "").strip()
        recent_replies = recent_replies_for_echo_check(
            session_history=self.session.history,
            window=self.config.repetition_window,
        )
        policy_result = apply_reply_policy(
            raw_reply=raw_reply,
            recent_replies=recent_replies,
            language=self.config.language,
            suppress_repeated_replies=self.config.suppress_repeated_replies,
            fallback_on_empty_reply=self.config.fallback_on_empty_reply,
        )

        trace = merge_policy_trace(
            trace=action_result.reaction_trace,
            suppress_reason=policy_result.suppress_reason,
            fallback_reason=policy_result.fallback_reason,
        )
        parse_failure = is_reaction_parse_failure(trace=action_result.reaction_trace)
        observability = self._build_observability(
            action_result=action_result,
            policy_suppress_reason=policy_result.suppress_reason,
            policy_fallback_reason=policy_result.fallback_reason,
            final_reply=policy_result.reply,
            speaker=speaker,
        )
        plan_diagnostics = observability.plan_diagnostics
        should_finish_dialogue = (
            self.session.dialogue_mode == "arc" and action_result.end_dialogue
        )

        if not policy_result.reply:
            silent_reason = ",".join(
                reason
                for reason in [
                    action_result.silent_reason,
                    policy_result.suppress_reason,
                ]
                if reason
            )
            if not silent_reason:
                silent_reason = "unknown"
            if should_finish_dialogue:
                self.session.finish_dialogue()
            return SimulationStepResult(
                now=now,
                speaker_name=speaker.name,
                trace=trace,
                reply="",
                silent_reason=silent_reason,
                parse_failure=parse_failure,
                observability=observability,
                plan_diagnostics=plan_diagnostics,
            )

        self.session.commit_speaker_reply(
            speaker=speaker,
            incoming_partner_utterance=incoming_partner_utterance,
            reply=policy_result.reply,
        )
        self.session.broadcast_reply(
            speaker=speaker,
            reply=policy_result.reply,
            now=now,
            language=self.config.language,
        )
        if should_finish_dialogue:
            self.session.finish_dialogue()
        return SimulationStepResult(
            now=now,
            speaker_name=speaker.name,
            trace=trace,
            reply=policy_result.reply,
            silent_reason="",
            parse_failure=parse_failure,
            observability=observability,
            plan_diagnostics=plan_diagnostics,
        )

    def _build_observability(
        self,
        *,
        action_result: ActionLoopResult,
        policy_suppress_reason: str,
        policy_fallback_reason: str,
        final_reply: str,
        speaker: SimAgent,
    ) -> SimulationStepObservability:
        diagnostics = action_result.diagnostics
        plan_diagnostics = self._build_plan_diagnostics(
            speaker=speaker,
            action_result=action_result,
        )
        return SimulationStepObservability(
            thought=diagnostics.thought if diagnostics else "",
            model_thought=diagnostics.model_thought if diagnostics else "",
            self_critique=diagnostics.self_critique if diagnostics else "",
            decision_reason=diagnostics.decision_reason if diagnostics else "",
            action_summary=diagnostics.action_summary if diagnostics else "",
            decision_process=self._build_decision_process(
                action_result=action_result,
                policy_suppress_reason=policy_suppress_reason,
                policy_fallback_reason=policy_fallback_reason,
                final_reply=final_reply,
            ),
            plan_diagnostics=plan_diagnostics,
        )

    def _build_plan_diagnostics(
        self,
        *,
        speaker: SimAgent,
        action_result: ActionLoopResult,
    ) -> dict[str, object]:
        profile = getattr(speaker, "profile", None)
        extended = getattr(profile, "extended", None)
        current_plan_context = list(getattr(extended, "current_plan_context", []))
        active_plan = current_plan_context[0] if current_plan_context else None
        end_dialogue_honored = (
            self.session.dialogue_mode == "arc" and action_result.end_dialogue
        )
        return {
            "dialogue_mode": self.session.dialogue_mode,
            "dialogue_goal": self.session.dialogue_goal,
            "dialogue_turns_taken": self.session.dialogue_turns_taken,
            "dialogue_target_turns": self.session.dialogue_target_turns,
            "model_requested_end_dialogue": action_result.end_dialogue,
            "end_dialogue_honored": end_dialogue_honored,
            "active_plan": active_plan,
            "current_plan_context": current_plan_context,
            "current_plan_item": action_result.current_plan_item,
            "plan_updated": action_result.plan_updated,
            "replan_reason": action_result.replan_reason,
        }

    def _build_decision_process(
        self,
        *,
        action_result: ActionLoopResult,
        policy_suppress_reason: str,
        policy_fallback_reason: str,
        final_reply: str,
    ) -> dict[str, object]:
        diagnostics = action_result.diagnostics
        base_process = dict(diagnostics.decision_process if diagnostics else {})
        base_process["policy"] = {
            "suppress_reason": policy_suppress_reason,
            "fallback_reason": policy_fallback_reason,
            "final_reply_empty": not bool(final_reply),
        }
        base_process["final_output"] = {
            "reply": final_reply,
            "action_intent": action_result.action_intent,
            "speak_decision": action_result.speak_decision,
            "end_dialogue": action_result.end_dialogue,
        }
        base_process["plan"] = {
            "current_plan_item": action_result.current_plan_item,
            "plan_updated": action_result.plan_updated,
            "replan_reason": action_result.replan_reason,
        }
        return base_process

    def _build_inactive_step_result(
        self,
        *,
        current_time: datetime.datetime,
        speaker: SimAgent,
    ) -> SimulationStepResult:
        now = current_time + datetime.timedelta(
            seconds=self.config.turn_time_step_seconds
        )
        plan_diagnostics = {
            "dialogue_mode": self.session.dialogue_mode,
            "dialogue_goal": self.session.dialogue_goal,
            "dialogue_turns_taken": self.session.dialogue_turns_taken,
            "dialogue_target_turns": self.session.dialogue_target_turns,
            "model_requested_end_dialogue": False,
            "end_dialogue_honored": False,
            "active_plan": None,
            "current_plan_context": [],
            "current_plan_item": "",
            "plan_updated": False,
            "replan_reason": "",
        }
        return SimulationStepResult(
            now=now,
            speaker_name=speaker.name,
            trace={"session_state": "ended"},
            reply="",
            silent_reason="dialogue_session_ended",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="",
                model_thought="",
                self_critique="",
                decision_reason="dialogue_session_ended",
                action_summary="continue_current_plan",
                decision_process={
                    "policy": {
                        "suppress_reason": "",
                        "fallback_reason": "",
                        "final_reply_empty": True,
                    },
                    "final_output": {
                        "reply": "",
                        "action_intent": "continue_current_plan",
                        "speak_decision": False,
                        "end_dialogue": False,
                    },
                },
                plan_diagnostics=plan_diagnostics,
            ),
            plan_diagnostics=plan_diagnostics,
        )

    def _run_action_loop(
        self,
        *,
        turn: int,
        now: datetime.datetime,
        speaker: SimAgent,
        speaking_partner: SimAgent,
        incoming_partner_utterance: str | None,
    ) -> ActionLoopResult:
        observed_events = build_turn_observed_events(
            language=self.config.language,
            speaker_name=speaker.name,
            partner_name=speaking_partner.name,
            incoming_partner_utterance=incoming_partner_utterance,
        )
        return speaker.brain.action_loop(
            ActionLoopInput(
                current_time=now,
                dialogue_history=self.session.dialogue_context_for(speaker=speaker),
                profile=speaker.profile,
                dialogue_arc=self.session.dialogue_arc_for(speaker=speaker),
                language=self.config.language,
                world_context=build_turn_world_context(
                    speaker_name=speaker.name,
                    partner_name=speaking_partner.name,
                    turn=turn,
                ),
                observed_entities=[speaking_partner.name],
                observed_events=observed_events,
            )
        )
