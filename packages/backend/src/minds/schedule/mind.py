"""ScheduleMind: 일정표·규칙으로 움직이는 마음. LLM을 부르지 않는다 (SPEC §12).

약속·소문·우호도는 `minds.social.SocialState`를 LLMMind와 함께 쓴다.
"""

import datetime
import random
from typing import Literal

from minds.social import (
    EncounterLog,
    EncounterRecord,
    SocialState,
    SpeechStyle,
    intent_for_slot,
    rule_choice,
)
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
        self._encounters = EncounterLog()
        self._rules = ReplyRules(
            social=self.social, config=config, rng=rng, style=style
        )

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        slot = self.social.agenda.slot_at(ctx.now)
        return intent_for_slot(slot, ctx.self_state.location_path)

    def plan_item_at(self, now: datetime.datetime) -> str | None:
        """지금 속한 일정표·약속 구간의 서술(읽기 전용)."""
        return self.social.agenda.slot_at(now).description

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        other_id = other.resident_id
        ruled = rule_choice(self.social, other_id, ctx.now, ctx.holidays)
        if ruled is not None:
            return self._encounters.add(self.social, other_id, ctx.now, *ruled)
        talkative = self._rng.random() < self.config.talkativeness
        return self._encounters.add(
            self.social,
            other_id,
            ctx.now,
            "converse" if talkative else "pass_by",
            "chance",
            f"수다 확률 {self.config.talkativeness:.2f}",
        )

    @property
    def encounter_log(self) -> tuple[EncounterRecord, ...]:
        """최근 조우 판정 기록(진단용). 행동 결정에는 쓰지 않는다."""
        return self._encounters.records

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
