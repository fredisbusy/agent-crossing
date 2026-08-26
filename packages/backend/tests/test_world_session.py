import datetime
from dataclasses import dataclass
from typing import cast

import pytest
from agents.agent import AgentProfile, ExtendedPersona, FixedPersona
from agents.reaction import DialogueArc
from agents.sim_agent import SimAgent
from world.session import (
    infer_dialogue_goal,
    WorldConversationSession,
    build_turn_observed_events,
    build_turn_world_context,
)


@dataclass(frozen=True)
class DummyAgent:
    name: str


@dataclass
class DummyBrain:
    queued: list[str]

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
class DummyInteractiveAgent:
    name: str
    profile: object
    brain: DummyBrain


def _profile(*, plans: list[str]) -> AgentProfile:
    return AgentProfile(
        fixed=FixedPersona(identity_stable_set=[]),
        extended=ExtendedPersona(
            lifestyle_and_routine=[],
            current_plan_context=plans,
        ),
    )


def test_dialogue_context_for_returns_full_history_when_window_is_none() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)

    session.dialogue_history_by_agent["Jiho"] = [
        ("안녕하세요", "안녕하세요"),
        ("오늘 어땠어요?", "도서관에 있었어요."),
    ]

    context = session.dialogue_context_for(speaker=agents[0])

    assert context == [
        ("안녕하세요", "안녕하세요"),
        ("오늘 어땠어요?", "도서관에 있었어요."),
    ]


def test_dialogue_context_for_respects_window_when_configured() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=1)

    session.dialogue_history_by_agent["Jiho"] = [
        ("안녕하세요", "안녕하세요"),
        ("오늘 어땠어요?", "도서관에 있었어요."),
    ]

    context = session.dialogue_context_for(speaker=agents[0])

    assert context == [("오늘 어땠어요?", "도서관에 있었어요.")]


def test_dialogue_turn_window_must_be_positive_if_provided() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])

    with pytest.raises(ValueError):
        _ = WorldConversationSession(agents=agents, dialogue_turn_window=0)


def test_session_requires_exactly_two_agents() -> None:
    """세션은 항상 정확히 한 쌍의 대화다 (N-agent 확장의 페어와이즈 전제)."""
    agents = cast(
        list[SimAgent],
        [DummyAgent(name="Jiho"), DummyAgent(name="Sujin"), DummyAgent(name="Minji")],
    )

    with pytest.raises(ValueError):
        _ = WorldConversationSession(agents=agents, dialogue_turn_window=None)

    with pytest.raises(ValueError):
        _ = WorldConversationSession(
            agents=cast(list[SimAgent], [DummyAgent(name="Jiho")]),
            dialogue_turn_window=None,
        )


def test_export_state_round_trips_into_a_fresh_session_for_the_same_pair() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    session.dialogue_goal = "산책 이야기"
    session.dialogue_turns_taken = 2

    saved = session.export_state()
    assert saved.participant_agent_names == ("Jiho", "Sujin")

    restored = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    restored.restore_state(saved)

    assert restored.dialogue_goal == "산책 이야기"
    assert restored.dialogue_turns_taken == 2


def test_restore_state_rejects_mismatched_participants() -> None:
    original_agents = cast(
        list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")]
    )
    saved = WorldConversationSession(
        agents=original_agents, dialogue_turn_window=None
    ).export_state()

    other_pair = cast(
        list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Minji")]
    )
    session = WorldConversationSession(agents=other_pair, dialogue_turn_window=None)

    with pytest.raises(ValueError, match="participants"):
        session.restore_state(saved)


def test_build_turn_world_context_uses_grounded_location_and_actions() -> None:
    context = build_turn_world_context(
        speaker_name="Jiho",
        partner_name="Sujin",
        location="브라이어 코브 > 수진의 집 > 거실",
        speaker_action="inside:수진의 집",
        partner_action="inside:수진의 집",
    )

    assert context["location"] == "브라이어 코브 > 수진의 집 > 거실"
    assert context["focus"] == "Jiho가 Sujin 쪽을 바라보고 있다"
    assert context["speaker_action"] == "inside:수진의 집"
    assert context["partner_action"] == "inside:수진의 집"


def test_build_turn_observed_events_uses_partner_utterance_when_available() -> None:
    events = build_turn_observed_events(
        language="en",
        partner_name="Sujin",
        incoming_partner_utterance="How was the decaf test?",
    )

    assert events == ["Heard Sujin's latest utterance: How was the decaf test?"]


def test_build_turn_observed_events_uses_encounter_goal_instead_of_stock_greeting() -> None:
    events = build_turn_observed_events(
        language="ko",
        partner_name="Sujin",
        incoming_partner_utterance=None,
        dialogue_goal="신메뉴 테스트의 진행 상황을 짧게 묻는다",
    )

    assert events == [
        "대화 시작 상대: Sujin; 맥락: 신메뉴 테스트의 진행 상황을 짧게 묻는다"
    ]
    assert "마주쳤다" not in events[0]


def test_infer_dialogue_goal_prefers_second_plan_context_when_available() -> None:
    speaker = cast(
        SimAgent,
        cast(
            object,
            DummyInteractiveAgent(
                name="Jiho",
                profile=_profile(
                    plans=[
                        "Jiho is visiting Morning Dew Cafe to talk with Sujin.",
                        "Jiho wants to ask how Sujin's new decaf blend is going.",
                    ]
                ),
                brain=DummyBrain(queued=[]),
            ),
        ),
    )

    assert (
        infer_dialogue_goal(speaker=speaker)
        == "Jiho wants to ask how Sujin's new decaf blend is going."
    )


def test_dialogue_arc_for_moves_into_closing_phase_near_target() -> None:
    speaker = cast(
        SimAgent,
        cast(
            object,
            DummyInteractiveAgent(
                name="Jiho",
                profile=_profile(
                    plans=[
                        "Jiho is visiting Morning Dew Cafe to talk with Sujin.",
                        "Jiho wants to ask how Sujin's new decaf blend is going.",
                    ]
                ),
                brain=DummyBrain(queued=[]),
            ),
        ),
    )
    partner = cast(
        SimAgent,
        cast(
            object,
            DummyInteractiveAgent(
                name="Sujin",
                profile=_profile(
                    plans=[
                        "Sujin is at Morning Dew Cafe and expecting Jiho to stop by.",
                    ]
                ),
                brain=DummyBrain(queued=[]),
            ),
        ),
    )
    session = WorldConversationSession(
        agents=[speaker, partner],
        dialogue_turn_window=None,
        dialogue_target_turns=5,
    )

    for reply in ["안녕", "반가워", "잘 지냈어"]:
        session.commit_speaker_reply(
            speaker=speaker,
            incoming_partner_utterance=None,
            reply=reply,
        )

    arc = session.dialogue_arc_for(speaker=speaker)

    assert arc == DialogueArc(
        goal="Jiho wants to ask how Sujin's new decaf blend is going.",
        turns_taken=3,
        target_turns=5,
        remaining_turns=2,
        phase="closing",
        should_wrap_up=True,
    )


def test_finish_dialogue_deactivates_session_and_clears_active_context() -> None:
    speaker = cast(
        SimAgent,
        cast(
            object,
            DummyInteractiveAgent(
                name="Jiho",
                profile=_profile(plans=["Greet Sujin briefly."]),
                brain=DummyBrain(queued=[]),
            ),
        ),
    )
    partner = cast(
        SimAgent,
        cast(
            object,
            DummyInteractiveAgent(
                name="Sujin",
                profile=_profile(plans=["Talk with Jiho."]),
                brain=DummyBrain(queued=[]),
            ),
        ),
    )
    session = WorldConversationSession(
        agents=[speaker, partner],
        dialogue_turn_window=None,
    )
    session.commit_speaker_reply(
        speaker=speaker,
        incoming_partner_utterance=None,
        reply="안녕",
    )

    session.finish_dialogue()

    assert session.is_active is False
    assert session.dialogue_turns_taken == 0
    assert session.dialogue_goal is None
    assert session.dialogue_context_for(speaker=speaker) == []
    assert session.dialogue_arc_for(speaker=speaker) is None


def test_broadcast_reply_enqueues_observations_and_incoming_queue() -> None:
    speaker = DummyInteractiveAgent(
        name="Jiho",
        profile=object(),
        brain=DummyBrain(queued=[]),
    )
    observer = DummyInteractiveAgent(
        name="Sujin",
        profile=object(),
        brain=DummyBrain(queued=[]),
    )
    agents = cast(list[SimAgent], [speaker, observer])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)

    session.broadcast_reply(
        speaker=cast(SimAgent, cast(object, speaker)),
        reply="안녕하세요",
        now=datetime.datetime(2026, 3, 3, 12, 0, 0),
        language="ko",
    )

    assert speaker.brain.queued == ["나는 이렇게 말했다: 안녕하세요"]
    assert observer.brain.queued == ["Jiho가 이렇게 말했다: 안녕하세요"]
    assert session.incoming_utterances_by_agent["Sujin"] == ["안녕하세요"]
