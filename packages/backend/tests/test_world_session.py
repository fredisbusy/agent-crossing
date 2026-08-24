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


def test_build_turn_world_context_rotates_locations() -> None:
    context = build_turn_world_context(
        speaker_name="Jiho",
        partner_name="Sujin",
        turn=5,
    )

    assert context["location"] == "Sujin 근처의 마을 광장"
    assert context["focus"] == "Jiho가 Sujin 쪽을 바라보고 있다"


def test_build_turn_observed_events_uses_partner_utterance_when_available() -> None:
    events = build_turn_observed_events(
        language="en",
        speaker_name="Jiho",
        partner_name="Sujin",
        incoming_partner_utterance="How was the decaf test?",
    )

    assert events == ["Heard Sujin's latest utterance: How was the decaf test?"]


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
