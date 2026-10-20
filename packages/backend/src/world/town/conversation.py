"""마을 대화 상태: 번갈아 말하다 None이 나오거나 max_turns에 닿으면 끝난다."""

from collections.abc import Sequence

from world.contracts import ConversationView, ResidentId, Utterance

DEFAULT_MAX_TURNS = 8


class TownConversation:
    """대화 하나의 진행 상태. 마음 호출과 관찰 전달은 `TownSimulation`이 한다."""

    def __init__(
        self,
        conversation_id: str,
        participant_ids: Sequence[ResidentId],
        *,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.conversation_id = conversation_id
        self.participant_ids: tuple[ResidentId, ...] = tuple(participant_ids)
        self.max_turns = max_turns
        self.history: list[Utterance] = []
        self.finished = False
        self._turn = 0

    @property
    def next_speaker_id(self) -> ResidentId:
        return self.participant_ids[self._turn % len(self.participant_ids)]

    def view(self) -> ConversationView:
        return ConversationView(
            conversation_id=self.conversation_id,
            participant_ids=self.participant_ids,
            history=tuple(self.history),
        )

    def record(self, utterance: Utterance | None) -> None:
        """차례의 결과를 기록한다. None이거나 상한에 닿으면 끝난다."""
        if utterance is None:
            self.finished = True
            return
        self.history.append(utterance)
        self._turn += 1
        if len(self.history) >= self.max_turns:
            self.finished = True
