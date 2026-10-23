"""ScheduleMind: 일정표·규칙으로 움직이는 마음. LLM을 부르지 않는다 (SPEC §12).

약속·소문·우호도는 `minds.social.SocialState`를 LLMMind와 함께 쓴다.
"""

import random
from typing import Literal

from minds.social import SocialState, SpeechStyle, intent_for_slot
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
        style: SpeechStyle | None = None,
    ) -> None:
        self.resident_id = resident_id
        self.display_name = display_name
        self.config = config
        self.social = SocialState(resident_id, Timetable(entries=tuple(config.entries)))
        self._rng = rng
        self._rules = ReplyRules(
            social=self.social, config=config, rng=rng, style=style
        )

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        slot = self.social.agenda.slot_at(ctx.now)
        return intent_for_slot(slot, ctx.self_state.location_path)

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        if self.social.friendship.in_cooldown(other.resident_id, ctx.now):
            return "pass_by"
        if self.social.talking_points(other.resident_id, ctx.now, ctx.holidays):
            return "converse"
        if self._rng.random() < self.config.talkativeness:
            return "converse"
        return "pass_by"

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        return self._rules.reply(ctx, conversation)

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        for obs in observations:
            if obs.kind == "utterance" and obs.utterance is not None:
                self.social.hear(obs.utterance, obs.observed_at)


def build_schedule_mind(
    *,
    resident_id: str,
    display_name: str,
    config: ScheduleConfig,
    rng: random.Random,
    style: SpeechStyle | None = None,
) -> ScheduleMind:
    return ScheduleMind(
        resident_id=resident_id,
        display_name=display_name,
        config=config,
        rng=rng,
        style=style,
    )
