"""LLMMind: 기억 스트림·검색·성찰·하루 계획으로 움직이는 마음 (SPEC §3~§7, §12).

약속·소문·우호도·선물·대화 멈춤 조건은 규칙 마음과 같은 `minds.social`을 쓴다.
이 마음이 따로 정하는 것은 하루 계획, 말을 걸지, 무엇을 말할지뿐이다.
LLM 호출은 동기 함수라 `asyncio.to_thread`로 돌린다.
"""

import asyncio
import datetime
from typing import Literal

from llm.clients.types import LlmGenerateOptions
from minds.social import (
    SocialState,
    intent_for_slot,
    must_end,
    partner_of,
    place_name,
    should_stop,
)
from world.contracts import (
    ActionIntent,
    ConversationView,
    EncounterChoice,
    MindContext,
    Observation,
    ResidentPublicView,
    SpeechAct,
    Utterance,
)

from .contracts import (
    DayPlanner,
    GenerateClient,
    LlmPersona,
    MemoryStore,
    ReflectionRunner,
)
from .parsing import ActResolver, parse_encounter, parse_speech
from .prompts import (
    Scene,
    build_encounter_prompt,
    build_speech_prompt,
    describe_events,
    describe_point,
)
from .routine import PlannedRoutine, plan_request, resolve_place

DEFAULT_MAX_TURNS = 6
"""한 대화에서 내가 말하는 최대 횟수. 마지막 말은 작별이다."""
RETRIEVE_TOP_K = 5
SPEECH_OPTIONS = LlmGenerateOptions(temperature=0.7, top_p=0.9, num_predict=512)
ENCOUNTER_OPTIONS = LlmGenerateOptions(temperature=0.0, top_p=1.0, num_predict=128)


class LLMMind:
    kind: Literal["llm"] = "llm"

    def __init__(
        self,
        *,
        persona: LlmPersona,
        client: GenerateClient,
        planner: DayPlanner,
        memory: MemoryStore,
        reflection: ReflectionRunner,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.persona = persona
        self.routine = PlannedRoutine(persona)
        self.social = SocialState(persona.resident_id, self.routine)
        self._client = client
        self._planner = planner
        self._memory = memory
        self._reflection = reflection
        self._max_turns = max_turns
        self._seeded = False

    # --- Mind 프로토콜 --------------------------------------------------------

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        await asyncio.to_thread(self._prepare_day, ctx)
        slot = self.social.agenda.slot_at(ctx.now)
        return intent_for_slot(slot, ctx.self_state.location_path)

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        if self.social.friendship.in_cooldown(other.resident_id, ctx.now):
            return "pass_by"
        if self.social.talking_points(other.resident_id, ctx.now, ctx.holidays):
            return "converse"
        converse = await asyncio.to_thread(self._ask_encounter, ctx, other)
        return "converse" if converse else "pass_by"

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        me = self.persona.resident_id
        other = partner_of(me, conversation)
        if other is None or should_stop(me, conversation):
            return None
        self.social.join_conversation(conversation.conversation_id, other, ctx.now)
        if conversation.history:
            self.social.hear(conversation.history[-1], ctx.now)
        return await asyncio.to_thread(self._speak, ctx, conversation, other)

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        for obs in observations:
            if obs.kind == "utterance" and obs.utterance is not None:
                self.social.hear(obs.utterance, obs.observed_at)
        await asyncio.to_thread(self._remember_all, observations)

    # --- 계획 -----------------------------------------------------------------

    def _prepare_day(self, ctx: MindContext) -> None:
        self._remember_seed(ctx.now)
        today = ctx.now.date()
        if self.routine.has_plan(today):
            return
        request = plan_request(
            self.persona,
            ctx.now,
            commitments=self.social.agenda.upcoming(ctx.now),
            holidays=ctx.holidays,
            yesterday=self._yesterday(ctx.now),
        )
        try:
            items = self._planner.generate_day_plan(request)
        except (RuntimeError, TimeoutError, ValueError):
            items = []
        slots = self.routine.set_plan(today, items)
        if slots:
            lines = [
                f"{s.start:%H:%M}-{s.end:%H:%M} {place_name(s.location_path)}: {s.description}"
                for s in slots
            ]
            summary = "; ".join(lines)
            self._store(
                f"{self.persona.display_name}의 오늘 계획: {summary}", ctx.now, "plan"
            )

    def _remember_seed(self, now: datetime.datetime) -> None:
        """시작 기억과 시작 사실(여는 행사 포함)을 기억 스트림에 한 번 넣는다."""
        if self._seeded:
            return
        self._seeded = True
        for text in self.persona.seed_memories:
            self._store(text, now)
        for fact in self.social.facts.all():
            if fact.source_resident_id == self.persona.resident_id:
                self._store(f"{fact.topic}: {fact.fact}", now)

    def _yesterday(self, now: datetime.datetime) -> str:
        found = self._memory.retrieve("어제 한 일", now, RETRIEVE_TOP_K)
        return " ".join(m.content for m in found)

    # --- 대화 -----------------------------------------------------------------

    def _scene(
        self, ctx: MindContext, partner_id: str, partner_name: str, query: str
    ) -> Scene:
        action = ctx.self_state.action
        return Scene(
            now=ctx.now,
            place=ctx.self_state.location_path,
            activity=action.description if action else "서 있다",
            holidays=ctx.holidays,
            partner=partner_name,
            friendship=self.social.friendship.score(partner_id),
            last_met=self.social.friendship.last_talk(partner_id),
            memories=self._memory.retrieve(query, ctx.now, RETRIEVE_TOP_K),
        )

    def _ask_encounter(self, ctx: MindContext, other: ResidentPublicView) -> bool:
        scene = self._scene(
            ctx, other.resident_id, other.display_name, other.display_name
        )
        prompt = build_encounter_prompt(
            self.persona,
            scene,
            partner_place=other.location_path,
            partner_activity=other.action_description or "서 있다",
        )
        return parse_encounter(self._generate(prompt, ENCOUNTER_OPTIONS))

    def _speak(
        self, ctx: MindContext, conversation: ConversationView, other: str
    ) -> Utterance | None:
        names = _names(ctx, conversation)
        history = conversation.history
        query = f"{names.get(other, other)} {history[-1].text if history else ''}"
        scene = self._scene(ctx, other, names.get(other, other), query)
        ending = must_end(self.persona.resident_id, conversation, self._max_turns)
        prompt = build_speech_prompt(
            self.persona,
            scene,
            events=self._event_lines(ctx.now),
            talking_points=[
                describe_point(p, ctx.now)
                for p in self.social.talking_points(other, ctx.now, ctx.holidays)
            ],
            history=[
                f"{names.get(u.speaker_id, u.speaker_id)}: {u.text}" for u in history
            ],
            must_end=ending,
        )
        draft = parse_speech(
            self._generate(prompt, SPEECH_OPTIONS), self._resolver(ctx)
        )
        if draft is None:
            return None
        acts = draft.acts
        if ending and all(a.kind != "farewell" for a in acts):
            acts = (*acts, SpeechAct(kind="farewell"))
        utterance = Utterance(
            speaker_id=self.persona.resident_id,
            listener_ids=(other,),
            text=draft.text,
            acts=acts,
            spoken_at=ctx.now,
        )
        self.social.said(utterance, ctx.now)
        partner = names.get(other, other)
        self._store(
            f'{self.persona.display_name}가 {partner}에게 말했다: "{draft.text}"',
            ctx.now,
        )
        return utterance

    def _event_lines(self, now: datetime.datetime) -> list[str]:
        upcoming = self.social.agenda.upcoming(now)
        hosting = [c.event for c in upcoming if c.role == "host"]
        attending = [c.event for c in upcoming if c.role == "guest"]
        mine = {(e.name, e.start_time) for e in hosting + attending}
        heard = [
            e
            for e in self.social.facts.events(now)
            if (e.name, e.start_time) not in mine
        ]
        return describe_events(hosting, attending, heard, now)

    def _resolver(self, ctx: MindContext) -> ActResolver:
        gifts = [h.gift_item for h in ctx.holidays if h.gift_item]
        return ActResolver(
            known_event=self.social.event_named,
            resolve_place=lambda text: resolve_place(text, self.persona),
            gift_item=gifts[0] if gifts else None,
        )

    # --- 기억 -----------------------------------------------------------------

    def _remember_all(self, observations: tuple[Observation, ...]) -> None:
        for obs in observations:
            spoken = obs.utterance
            if spoken is not None and spoken.speaker_id == self.persona.resident_id:
                continue
            self._store(obs.text, obs.observed_at)
        if observations and self._reflection.should_reflect():
            self._reflection.reflect(now=observations[-1].observed_at)

    def _store(
        self, text: str, now: datetime.datetime, kind: str = "observation"
    ) -> None:
        importance = self._memory.remember(text, now, kind=kind)
        self._reflection.record_observation_importance(importance)

    def _generate(self, prompt: str, options: LlmGenerateOptions) -> str:
        try:
            return self._client.generate(
                prompt=prompt, options=options, format_json=True
            )
        except (RuntimeError, TimeoutError, ValueError):
            return ""


def _names(ctx: MindContext, conversation: ConversationView) -> dict[str, str]:
    names = {view.resident_id: view.display_name for view in ctx.nearby}
    names[ctx.self_state.resident_id] = ctx.self_state.display_name
    for resident_id in conversation.participant_ids:
        names.setdefault(resident_id, resident_id.replace("_", " ").title())
    return names
