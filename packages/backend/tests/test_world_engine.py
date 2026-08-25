import datetime
from dataclasses import dataclass
from typing import Literal, cast

from agents.brain import ActionLoopInput, ActionLoopResult
from agents.reaction import ReactionDecision, ReactionDecisionTrace
from agents.sim_agent import SimAgent
from world.engine import SimulationEngine, SimulationEngineConfig
from world.session import WorldConversationSession


@dataclass
class DummyBrain:
    next_result: ActionLoopResult
    queued: list[str]
    last_input: ActionLoopInput | None = None
    next_reaction_decision: ReactionDecision | None = None

    def action_loop(
        self, input: ActionLoopInput
    ) -> tuple[ActionLoopResult, ReactionDecision | None]:
        self.last_input = input
        return self.next_result, self.next_reaction_decision

    def queue_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        profile: object,
    ) -> None:
        _ = now
        _ = profile
        self.queued.append(content)


@dataclass
class DummyAgent:
    name: str
    profile: object
    brain: DummyBrain


def _reaction_decision(*, thought: str = "") -> ReactionDecision:
    return ReactionDecision(
        should_react=True,
        reaction="",
        reason=thought,
        trace=ReactionDecisionTrace(raw_response="", parse_success=True),
    )


def _engine_config(
    *,
    suppress_repeated_replies: bool = False,
    fallback_on_empty_reply: bool = False,
) -> SimulationEngineConfig:
    return SimulationEngineConfig(
        language=cast(Literal["ko", "en"], "ko"),
        turn_time_step_seconds=45,
        suppress_repeated_replies=suppress_repeated_replies,
        repetition_window=4,
        fallback_on_empty_reply=fallback_on_empty_reply,
    )


def test_step_commits_reply_and_broadcasts_to_partner() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="안녕하세요",
                utterance="안녕하세요",
            ),
            next_reaction_decision=_reaction_decision(thought="반갑게 인사"),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk=None,
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    engine = SimulationEngine(session=session, config=_engine_config())

    result = engine.step(
        turn=1,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == "안녕하세요"
    assert result.silent_reason == ""
    assert session.history == [("Jiho", "안녕하세요")]
    assert speaker.brain.last_input is not None
    assert speaker.brain.last_input.dialogue_arc is not None
    assert speaker.brain.last_input.dialogue_arc.phase == "opening"
    assert speaker.brain.last_input.dialogue_arc.target_turns == 5
    assert speaker.brain.queued == ["나는 이렇게 말했다: 안녕하세요"]
    assert partner.brain.queued == ["Jiho가 이렇게 말했다: 안녕하세요"]


def test_step_suppresses_repeated_reply_when_policy_enabled() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="안녕하세요",
                utterance="안녕하세요",
                silent_reason="",
            ),
            next_reaction_decision=_reaction_decision(),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk=None,
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    session.history.append(("Sujin", "안녕하세요"))
    engine = SimulationEngine(
        session=session,
        config=_engine_config(suppress_repeated_replies=True),
    )

    result = engine.step(
        turn=2,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == ""
    assert "repeat_echo_suppressed" in result.silent_reason
    assert session.history == [("Sujin", "안녕하세요")]


def test_step_suppresses_meta_leak_reply() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="안녕하세요, Jiho. 커피는一如既往地生成回答：{",
                utterance="안녕하세요, Jiho. 커피는一如既往地生成回答：{",
                silent_reason="",
            ),
            next_reaction_decision=_reaction_decision(),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk=None,
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    engine = SimulationEngine(session=session, config=_engine_config())

    result = engine.step(
        turn=1,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == ""
    assert "invalid_reply_content" in result.silent_reason
    assert result.trace.get("suppress_reason") == "invalid_reply_content"
    assert session.history == []


def test_step_suppresses_english_only_reply_in_korean_runtime() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="Hello, how are you today?",
                utterance="Hello, how are you today?",
            ),
            next_reaction_decision=_reaction_decision(),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk=None,
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    engine = SimulationEngine(session=session, config=_engine_config())

    result = engine.step(
        turn=1,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == ""
    assert "language_policy_violation" in result.silent_reason
    assert session.history == []


def test_step_fallbacks_when_meta_leak_reply_and_fallback_enabled() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="안녕하세요, Jiho. 커피는一如既往地生成回答：{",
                utterance="안녕하세요, Jiho. 커피는一如既往地生成回答：{",
                silent_reason="",
            ),
            next_reaction_decision=_reaction_decision(),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk=None,
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    engine = SimulationEngine(
        session=session,
        config=_engine_config(fallback_on_empty_reply=True),
    )

    result = engine.step(
        turn=1,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == "LLM 응답 오류"
    assert result.trace.get("suppress_reason") == "invalid_reply_content"
    assert result.trace.get("fallback_reason") == "empty_reply_fallback"
    assert session.history == [("Jiho", "LLM 응답 오류")]


def test_step_finishes_session_when_action_marks_dialogue_end() -> None:
    speaker = DummyAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="그럼 난 이만 가볼게.",
                utterance="그럼 난 이만 가볼게.",
                end_dialogue=True,
            ),
            next_reaction_decision=_reaction_decision(thought="마무리"),
            queued=[],
            last_input=None,
        ),
    )
    partner = DummyAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(
            next_result=ActionLoopResult(
                current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                talk="다음에 봐",
            ),
            queued=[],
            last_input=None,
        ),
    )
    session = WorldConversationSession(
        agents=cast(list[SimAgent], [speaker, partner]),
        dialogue_turn_window=None,
    )
    engine = SimulationEngine(session=session, config=_engine_config())

    result = engine.step(
        turn=1,
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        speaker=cast(SimAgent, cast(object, speaker)),
        speaking_partner=cast(SimAgent, cast(object, partner)),
    )

    assert result.reply == "그럼 난 이만 가볼게."
    assert session.is_active is False
    assert session.dialogue_context_for(
        speaker=cast(SimAgent, cast(object, speaker))
    ) == []

    follow_up = engine.step(
        turn=2,
        current_time=result.now,
        speaker=cast(SimAgent, cast(object, partner)),
        speaking_partner=cast(SimAgent, cast(object, speaker)),
    )

    assert follow_up.reply == ""
    assert follow_up.silent_reason == "dialogue_session_ended"
    assert partner.brain.last_input is None
