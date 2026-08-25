import datetime
from typing import Literal

from agents.reaction import DialogueArc
from agents.sim_agent import SimAgent
from world.observation_builder import format_other_said, format_self_said
from persistence.contracts import ConversationSave

DEFAULT_DIALOGUE_TARGET_TURNS = 5


def infer_dialogue_goal(*, speaker: SimAgent) -> str:
    profile = getattr(speaker, "profile", None)
    if profile is None:
        return "짧고 친근하게 대화한 뒤 현재 계획으로 돌아간다."

    extended = getattr(profile, "extended", None)
    if extended is None:
        return "짧고 친근하게 대화한 뒤 현재 계획으로 돌아간다."

    current_plan_context = getattr(extended, "current_plan_context", [])
    if len(current_plan_context) >= 2 and current_plan_context[1].strip():
        return current_plan_context[1].strip()
    if current_plan_context and current_plan_context[0].strip():
        return current_plan_context[0].strip()
    return "짧고 친근하게 대화한 뒤 현재 계획으로 돌아간다."


def build_turn_world_context(
    *, speaker_name: str, partner_name: str, turn: int
) -> dict[str, str]:
    locations = [
        "마을 광장",
        "카페 입구",
        "도서관 산책로",
        "공원 벤치",
    ]
    location = locations[(turn - 1) % len(locations)]
    return {
        "location": f"{partner_name} 근처의 {location}",
        "focus": f"{speaker_name}가 {partner_name} 쪽을 바라보고 있다",
    }


def build_turn_observed_events(
    *,
    language: Literal["ko", "en"],
    speaker_name: str,
    partner_name: str,
    incoming_partner_utterance: str | None,
) -> list[str]:
    if incoming_partner_utterance and incoming_partner_utterance.strip():
        if language == "ko":
            return [f"{partner_name}의 직전 발화를 들음: {incoming_partner_utterance}"]
        return [
            f"Heard {partner_name}'s latest utterance: {incoming_partner_utterance}"
        ]

    if language == "ko":
        return [f"{speaker_name}가 {partner_name}를 근처에서 마주쳤다."]
    return [f"{speaker_name} encountered {partner_name} nearby."]


class WorldConversationSession:
    def __init__(
        self,
        *,
        agents: list[SimAgent],
        dialogue_turn_window: int | None,
        dialogue_target_turns: int = DEFAULT_DIALOGUE_TARGET_TURNS,
    ):
        if len(agents) < 2:
            raise ValueError("At least two agents are required")
        if dialogue_turn_window is not None and dialogue_turn_window < 1:
            raise ValueError("dialogue_turn_window must be at least 1")
        if dialogue_target_turns < 2:
            raise ValueError("dialogue_target_turns must be at least 2")

        self.agents: list[SimAgent] = agents
        self.dialogue_turn_window: int | None = dialogue_turn_window
        self.dialogue_target_turns: int = dialogue_target_turns
        self.is_active: bool = True
        self.turn_index: int = 0
        self.history: list[tuple[str, str]] = []
        self.dialogue_turns_taken: int = 0
        self.dialogue_goal: str | None = None
        self.dialogue_history_by_agent: dict[str, list[tuple[str, str]]] = {
            agent.name: [] for agent in agents
        }
        self.incoming_utterances_by_agent: dict[str, list[str]] = {
            agent.name: [] for agent in agents
        }

    def start_dialogue(self) -> bool:
        if self.is_active:
            return False
        self.is_active = True
        self.dialogue_turns_taken = 0
        self.dialogue_goal = None
        return True

    def next_speaker(self) -> SimAgent:
        speaker = self.agents[self.turn_index % len(self.agents)]
        self.turn_index += 1
        return speaker

    def consume_incoming_partner_utterance(
        self,
        *,
        speaker: SimAgent,
    ) -> str | None:
        if not self.is_active:
            return None

        incoming_queue = self.incoming_utterances_by_agent[speaker.name]
        if not incoming_queue:
            return None

        incoming_partner_utterance = incoming_queue.pop(0)
        self.dialogue_history_by_agent[speaker.name].append(
            (incoming_partner_utterance, "")
        )
        return incoming_partner_utterance

    def dialogue_context_for(
        self,
        *,
        speaker: SimAgent,
    ) -> list[tuple[str, str]]:
        if not self.is_active:
            return []

        history = self.dialogue_history_by_agent[speaker.name]
        if self.dialogue_turn_window is None:
            return history
        return history[-self.dialogue_turn_window :]

    def dialogue_arc_for(
        self,
        *,
        speaker: SimAgent,
    ) -> DialogueArc | None:
        if not self.is_active:
            return None

        if self.dialogue_goal is None:
            self.dialogue_goal = infer_dialogue_goal(speaker=speaker)

        remaining_turns = max(0, self.dialogue_target_turns - self.dialogue_turns_taken)
        if self.dialogue_turns_taken < 2:
            phase: Literal["opening", "middle", "closing"] = "opening"
        elif remaining_turns <= 2:
            phase = "closing"
        else:
            phase = "middle"

        return DialogueArc(
            goal=self.dialogue_goal,
            turns_taken=self.dialogue_turns_taken,
            target_turns=self.dialogue_target_turns,
            remaining_turns=remaining_turns,
            phase=phase,
            should_wrap_up=(phase == "closing"),
        )

    def commit_speaker_reply(
        self,
        *,
        speaker: SimAgent,
        incoming_partner_utterance: str | None,
        reply: str,
    ) -> None:
        if not self.is_active:
            return

        if self.dialogue_goal is None:
            self.dialogue_goal = infer_dialogue_goal(speaker=speaker)

        if incoming_partner_utterance is not None:
            self.dialogue_history_by_agent[speaker.name][-1] = (
                incoming_partner_utterance,
                reply,
            )
        else:
            self.dialogue_history_by_agent[speaker.name].append(("", reply))

        self.history.append((speaker.name, reply))
        self.dialogue_turns_taken += 1

    def finish_dialogue(self) -> None:
        self.is_active = False
        self.dialogue_turns_taken = 0
        self.dialogue_goal = None
        self.dialogue_history_by_agent = {agent.name: [] for agent in self.agents}
        self.incoming_utterances_by_agent = {agent.name: [] for agent in self.agents}

    def broadcast_reply(
        self,
        *,
        speaker: SimAgent,
        reply: str,
        now: datetime.datetime,
        language: Literal["ko", "en"],
    ) -> None:
        for observer in self.agents:
            if observer is speaker:
                observer.brain.queue_observation(
                    content=format_self_said(language, reply),
                    now=now,
                    profile=observer.profile,
                )
                continue

            observer.brain.queue_observation(
                content=format_other_said(language, speaker.name, reply),
                now=now,
                profile=observer.profile,
            )
            self.incoming_utterances_by_agent[observer.name].append(reply)

    def export_state(self) -> ConversationSave:
        return ConversationSave(
            is_active=self.is_active,
            turn_index=self.turn_index,
            dialogue_turn_window=self.dialogue_turn_window,
            dialogue_target_turns=self.dialogue_target_turns,
            dialogue_turns_taken=self.dialogue_turns_taken,
            dialogue_goal=self.dialogue_goal,
            history=list(self.history),
            dialogue_history_by_agent={
                name: list(history)
                for name, history in self.dialogue_history_by_agent.items()
            },
            incoming_utterances_by_agent={
                name: list(queue)
                for name, queue in self.incoming_utterances_by_agent.items()
            },
        )

    def restore_state(self, state: ConversationSave) -> None:
        known_agents = {agent.name for agent in self.agents}
        if set(state.dialogue_history_by_agent) != known_agents:
            raise ValueError("dialogue history agent roster does not match runtime")
        if set(state.incoming_utterances_by_agent) != known_agents:
            raise ValueError("incoming dialogue queue roster does not match runtime")
        self.is_active = state.is_active
        self.turn_index = state.turn_index
        self.dialogue_turn_window = state.dialogue_turn_window
        self.dialogue_target_turns = state.dialogue_target_turns
        self.dialogue_turns_taken = state.dialogue_turns_taken
        self.dialogue_goal = state.dialogue_goal
        self.history = list(state.history)
        self.dialogue_history_by_agent = {
            name: list(history)
            for name, history in state.dialogue_history_by_agent.items()
        }
        self.incoming_utterances_by_agent = {
            name: list(queue)
            for name, queue in state.incoming_utterances_by_agent.items()
        }
