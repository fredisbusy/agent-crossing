"""ScheduleMind: 일정표·규칙으로 움직이는 마음. LLM을 부르지 않는다 (SPEC §12)."""

import random
from typing import Literal

from world.contracts import (
    ActionIntent,
    ConversationView,
    EncounterChoice,
    MindContext,
    Observation,
    ResidentId,
    ResidentPublicView,
    Utterance,
)

from .config import ScheduleConfig
from .facts import FactStore
from .friendship import Friendship
from .lines import place_name
from .rules import ReplyRules
from .timetable import Timetable


class ScheduleMind:
    kind: Literal["schedule"] = "schedule"

    def __init__(
        self,
        *,
        resident_id: ResidentId,
        display_name: str,
        config: ScheduleConfig,
        rng: random.Random,
    ) -> None:
        self.resident_id = resident_id
        self.display_name = display_name
        self.config = config
        self.timetable = Timetable(entries=tuple(config.entries))
        self.friendship = Friendship()
        self.facts = FactStore()
        self._rng = rng
        self._rules = ReplyRules(
            resident_id=resident_id,
            config=config,
            timetable=self.timetable,
            friendship=self.friendship,
            facts=self.facts,
            rng=rng,
        )

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        slot = self.timetable.slot_at(ctx.now)
        here = ctx.self_state.location_path
        at_place = here == slot.location_path or here.startswith(
            slot.location_path + " > "
        )
        if not at_place:
            return ActionIntent(
                kind="move",
                description=f"{place_name(slot.location_path)} 쪽으로 이동한다",
                location_path=slot.location_path,
                until=slot.end,
                emoji=slot.emoji,
            )
        return ActionIntent(
            kind=slot.action,
            description=slot.description,
            location_path=slot.location_path,
            until=slot.end,
            emoji=slot.emoji,
        )

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        if self.friendship.in_cooldown(other.resident_id, ctx.now):
            return "pass_by"
        if self.facts.unshared_for(other.resident_id):
            return "converse"
        if self._rng.random() < self.config.talkativeness:
            return "converse"
        return "pass_by"

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        return self._rules.reply(ctx.now, conversation)

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        for obs in observations:
            utterance = obs.utterance
            if obs.kind != "utterance" or utterance is None:
                continue
            if utterance.speaker_id == self.resident_id:
                continue
            for act in utterance.acts:
                if act.kind == "share_fact" and act.topic and act.fact:
                    self.facts.learn(
                        act.topic, act.fact, utterance.speaker_id, obs.observed_at
                    )


def build_schedule_mind(
    *,
    resident_id: str,
    display_name: str,
    config: ScheduleConfig,
    rng: random.Random,
) -> ScheduleMind:
    return ScheduleMind(
        resident_id=resident_id, display_name=display_name, config=config, rng=rng
    )
