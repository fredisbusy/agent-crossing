"""마을 틱 루프 (SPEC §14): 이동 → 지각 → 조우·대화 → 마음 깨우기 → 의도 적용."""

import asyncio
import json
import random
from collections import Counter
from collections.abc import Coroutine, Sequence
from typing import Any, Literal

from world.contracts import (
    ActionIntent,
    MindContext,
    MindKind,
    Space,
    Utterance,
    WorldSnapshot,
    ResidentSnapshot,
)
from world.residents import Resident

from .clock import SimClock
from .conversation import DEFAULT_MAX_TURNS, TownConversation
from .encounters import EncounterTracker, can_talk
from .perception import (
    DEFAULT_PERCEPTION_RADIUS,
    is_near,
    near_pairs,
    sight_observation,
    sight_signature,
    utterance_observation,
)

SimulationMode = Literal["faithful"]


class TownSimulation:
    """공간·주민·시계·난수를 주입받아 1분 단위로 마을을 진행한다."""

    def __init__(
        self,
        *,
        space: Space,
        residents: Sequence[Resident],
        clock: SimClock,
        rng: random.Random,
        mode: SimulationMode = "faithful",
        perception_radius: int = DEFAULT_PERCEPTION_RADIUS,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.space = space
        self.residents = list(residents)
        self.clock = clock
        self.mode = mode
        self.tick_count = 0
        self.mind_calls: Counter[MindKind] = Counter()
        """마음 종류별 호출 수(next_action·on_encounter·respond 합계)."""
        self._rng = rng
        self._radius = perception_radius
        self._max_turns = max_turns
        self._by_id = {resident.resident_id: resident for resident in self.residents}
        self._tracker = EncounterTracker()
        self._conversations: list[TownConversation] = []
        self._conversation_serial = 0
        self._near: dict[str, list[str]] = {}
        self._seen: dict[str, dict[str, tuple[str, str | None]]] = {}
        self._spoken: dict[str, tuple[int, str]] = {}

    async def tick(self) -> None:
        self.clock.advance(1)
        self.tick_count += 1
        for resident in self.residents:
            resident.body.step()
        pairs = near_pairs(self.residents, self._radius)
        self._perceive(pairs)
        await self._encounters(pairs)
        await self._advance_conversations()
        await self._wake_minds()

    async def run_minutes(self, minutes: int) -> None:
        for _ in range(minutes):
            await self.tick()

    def snapshot(self) -> WorldSnapshot:
        residents: list[ResidentSnapshot] = []
        for resident in self.residents:
            state = resident.body.state
            spoken = self._spoken.get(resident.resident_id)
            residents.append(
                ResidentSnapshot(
                    resident_id=resident.resident_id,
                    display_name=state.display_name,
                    tile=state.tile,
                    location_path=state.location_path,
                    action_description=state.action.description if state.action else None,
                    emoji=state.action.emoji if state.action else None,
                    utterance_text=spoken[1] if spoken and spoken[0] == self.tick_count else None,
                    mind_kind=resident.config.mind,
                )
            )
        return WorldSnapshot(
            tick=self.tick_count, sim_time=self.clock.now, residents=tuple(residents)
        )

    def text_state(self) -> str:
        """QA용 짧은 JSON 상태."""
        return json.dumps(
            {
                "tick": self.tick_count,
                "time": self.clock.now.isoformat(),
                "residents": [
                    {
                        "id": r.resident_id,
                        "location": r.body.state.location_path,
                        "action": r.body.state.action.description if r.body.state.action else None,
                        "in_conversation": r.body.conversation_id is not None,
                    }
                    for r in self.residents
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # --- 지각 ---------------------------------------------------------------

    def _perceive(self, pairs: set[tuple[str, str]]) -> None:
        self._near = {r.resident_id: [] for r in self.residents}
        for a_id, b_id in sorted(pairs):
            self._near[a_id].append(b_id)
            self._near[b_id].append(a_id)
        for observer in self.residents:
            seen = self._seen.setdefault(observer.resident_id, {})
            near_ids = sorted(self._near[observer.resident_id])
            for gone in set(seen) - set(near_ids):
                del seen[gone]
            where = observer.body.state.location_path
            for other_id in near_ids:
                other = self._by_id[other_id]
                signature = sight_signature(other)
                if seen.get(other_id) != signature:
                    seen[other_id] = signature
                    observer.pending.append(
                        sight_observation(other, self.clock.now, where)
                    )

    def _context(self, resident: Resident, *, drain: bool) -> MindContext:
        observations = (
            resident.drain_observations() if drain else tuple(resident.pending)
        )
        return MindContext(
            now=self.clock.now,
            self_state=resident.body.state,
            nearby=tuple(
                self._by_id[i].public_view()
                for i in sorted(self._near.get(resident.resident_id, []))
            ),
            observations=observations,
        )

    async def _observe_drained(self, resident: Resident) -> MindContext:
        ctx = self._context(resident, drain=True)
        if ctx.observations:
            await resident.mind.observe(ctx.observations)
        return ctx

    # --- 조우와 대화 ----------------------------------------------------------

    async def _encounters(self, pairs: set[tuple[str, str]]) -> None:
        self._tracker.forget_apart(pairs)
        for pair in self._tracker.candidates(pairs):
            a, b = self._by_id[pair[0]], self._by_id[pair[1]]
            if not can_talk(a, b):
                continue
            self._tracker.settle(pair)
            if self._tracker.on_cooldown(pair, self.clock.now):
                continue
            self._tracker.mark_asked(pair, self.clock.now)
            self.mind_calls[a.config.mind] += 1
            self.mind_calls[b.config.mind] += 1
            choice_a, choice_b = await asyncio.gather(
                a.mind.on_encounter(self._context(a, drain=False), b.public_view()),
                b.mind.on_encounter(self._context(b, drain=False), a.public_view()),
            )
            if choice_a == "converse" and choice_b == "converse":
                self._start_conversation(a, b)

    def _start_conversation(self, a: Resident, b: Resident) -> None:
        self._conversation_serial += 1
        first, second = self._rng.sample([a, b], 2)
        conversation = TownConversation(
            f"conv-{self._conversation_serial}",
            (first.resident_id, second.resident_id),
            max_turns=self._max_turns,
        )
        for member in (a, b):
            member.body.conversation_id = conversation.conversation_id
        self._conversations.append(conversation)

    async def _advance_conversations(self) -> None:
        active = [c for c in self._conversations if not c.finished]
        if not active:
            return
        calls: list[Coroutine[Any, Any, Utterance | None]] = []
        for conversation in active:
            speaker = self._by_id[conversation.next_speaker_id]
            self.mind_calls[speaker.config.mind] += 1
            ctx = await self._observe_drained(speaker)
            calls.append(speaker.mind.respond(ctx, conversation.view()))
        results = await asyncio.gather(*calls)
        for conversation, utterance in zip(active, results):
            conversation.record(utterance)
            if utterance is not None:
                self._deliver(conversation, utterance)
            if conversation.finished:
                for member_id in conversation.participant_ids:
                    self._by_id[member_id].body.conversation_id = None
        self._conversations = [c for c in self._conversations if not c.finished]

    def _deliver(self, conversation: TownConversation, utterance: Utterance) -> None:
        speaker = self._by_id[utterance.speaker_id]
        self._spoken[speaker.resident_id] = (self.tick_count, utterance.text)
        for receiver in self.residents:
            if receiver is speaker:
                continue
            heard = receiver.resident_id in conversation.participant_ids or is_near(
                speaker, receiver, self._radius
            )
            if heard:
                receiver.pending.append(
                    utterance_observation(
                        utterance,
                        speaker.config.display_name,
                        receiver.body.state.location_path,
                    )
                )

    # --- 마음 깨우기 ----------------------------------------------------------

    async def _wake_minds(self) -> None:
        woken = [
            r
            for r in self.residents
            if r.body.conversation_id is None
            and (r.pending or r.body.is_expired(self.clock.now))
        ]
        if not woken:
            return
        calls: list[Coroutine[Any, Any, ActionIntent]] = []
        for resident in woken:
            self.mind_calls[resident.config.mind] += 1
            ctx = await self._observe_drained(resident)
            calls.append(resident.mind.next_action(ctx))
        intents = await asyncio.gather(*calls)
        for resident, intent in zip(woken, intents):
            failure = resident.body.set_intent(intent, self.clock.now)
            if failure is not None:
                resident.pending.append(failure)
