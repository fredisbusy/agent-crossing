"""관찰에 반응할지 판정하고, 반응하면 지금 이후 계획만 다시 세운다 (논문 §4.3.1, SPEC §7, §14).

깨움당 판정은 최대 1회(LLM 1회), 반응 시 재계획 1회가 더 든다. 판정 근거는 도메인 결과가 아닌
진단 버퍼(`ReactionRecord`)에만 남긴다 (AGENTS.md §9).
"""

import datetime
import json
import math
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import cast

from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from llm.clients.types import LlmGenerateOptions
from llm.template_loader import render_template
from minds.social import Slot, format_time, josa, place_name
from world.contracts import MindContext, Observation

from ..contracts import DayPlanner, GenerateClient, LlmPersona, MemoryStore
from ..prompts import persona_text
from ..recall import MemoryWriter
from .decompose import Decomposer
from .routine import PlannedRoutine, find_place

REACTION_TOP_K = 5
"""판정 프롬프트에 싣는 관련 기억 수."""
MIN_REACTION_MINUTES = 5
MAX_REACTION_MINUTES = 120
REACTION_LOG_SIZE = 20
"""진단 버퍼에 남기는 최근 판정 수."""
SUMMARY_MAX_CHARS = 120
"""기억·진단에 남기는 관찰 요약의 최대 길이."""
REACTION_OPTIONS = LlmGenerateOptions(temperature=0.0, top_p=1.0, num_predict=256)
_JUDGED_KINDS = ("sight", "event")
_RECOVERABLE = (RuntimeError, TimeoutError, ValueError)


@dataclass(frozen=True)
class ReactionRecord:
    """판정 한 번의 진단 기록 (TODO 3-B). 행동 결정(ActionIntent)에는 섞지 않는다."""

    at: datetime.datetime
    react: bool
    reason: str
    observations: str


@dataclass(frozen=True)
class Reaction:
    description: str
    location: str
    minutes: int


@dataclass(frozen=True)
class Verdict:
    react: bool
    reason: str
    reaction: Reaction | None


class Reactor:
    """동기 호출을 한다. `asyncio.to_thread` 안에서 부른다."""

    def __init__(
        self,
        *,
        persona: LlmPersona,
        client: GenerateClient,
        planner: DayPlanner,
        memory: MemoryStore,
        writer: MemoryWriter,
        routine: PlannedRoutine,
        decomposer: Decomposer,
    ) -> None:
        self._persona = persona
        self._client = client
        self._planner = planner
        self._memory = memory
        self._writer = writer
        self._routine = routine
        self._decomposer = decomposer
        self._log: deque[ReactionRecord] = deque(maxlen=REACTION_LOG_SIZE)
        self.items: set[DayPlanItem] = set()
        """반응으로 끼워 넣은 계획 항목. 짧아서 다시 쪼개지 않는다."""

    @property
    def log(self) -> tuple[ReactionRecord, ...]:
        return tuple(self._log)

    def new_sights(self, ctx: MindContext) -> list[Observation]:
        """이번 깨움에서 판정할 관찰: 시야·사건. 발화와 내 관찰은 뺀다."""
        me = self._persona.resident_id
        return [
            o
            for o in ctx.observations
            if o.kind in _JUDGED_KINDS and o.subject_id != me
        ]

    def react(
        self,
        ctx: MindContext,
        slot: Slot,
        *,
        summary: str,
        make_request: Callable[[], DayPlanBroadStrokesRequest],
    ) -> bool:
        """새 관찰에 반응해 계획을 바꿨으면 True. 잠·약속 중이거나 볼 것이 없으면 LLM을 부르지 않는다."""
        self.items = {i for i in self.items if i.end_time.date() >= ctx.now.date()}
        seen = self.new_sights(ctx)
        if not seen or slot.action == "sleep" or slot.is_commitment:
            return False
        verdict = self._judge(ctx, slot, seen, summary)
        digest = _digest(seen)
        self._log.append(ReactionRecord(ctx.now, verdict.react, verdict.reason, digest))
        if not verdict.react or verdict.reaction is None:
            return False
        self._apply(ctx, verdict.reaction, digest, make_request)
        return True

    # --- 판정 -------------------------------------------------------------------

    def _judge(
        self, ctx: MindContext, slot: Slot, seen: Sequence[Observation], summary: str
    ) -> Verdict:
        self._writer.flush()
        query = " ".join(o.text for o in seen)
        found = self._memory.retrieve(query, ctx.now, REACTION_TOP_K)
        action = ctx.self_state.action
        prompt = render_template(
            "town_reaction.md",
            persona=persona_text(self._persona, summary),
            name=self._persona.display_name,
            now=f"{ctx.now.month}월 {ctx.now.day}일 {format_time(ctx.now)}",
            place=place_name(ctx.self_state.location_path),
            activity=action.description if action else slot.description,
            observations="\n".join(f"{i}. {o.text}" for i, o in enumerate(seen, 1)),
            memories="\n".join(f"- {m.content}" for m in found) or "- (없음)",
        )
        try:
            raw = self._client.generate(
                prompt=prompt, options=REACTION_OPTIONS, format_json=True
            )
        except _RECOVERABLE:
            return Verdict(False, "판정 실패", None)
        return parse_verdict(raw)

    # --- 재계획 -----------------------------------------------------------------

    def _apply(
        self,
        ctx: MindContext,
        reaction: Reaction,
        digest: str,
        make_request: Callable[[], DayPlanBroadStrokesRequest],
    ) -> None:
        now = ctx.now
        start = now.replace(second=0, microsecond=0)
        minutes = max(MIN_REACTION_MINUTES, min(MAX_REACTION_MINUTES, reaction.minutes))
        midnight = start.replace(hour=0, minute=0) + datetime.timedelta(days=1)
        end = min(start + datetime.timedelta(minutes=minutes), midnight)
        place = (
            find_place(reaction.location, self._persona) or ctx.self_state.location_path
        )
        item = DayPlanItem(start, end, place, reaction.description)
        later = self._replan(now, item, make_request) if end < midnight else []
        if later is None:
            later = self._trimmed_rest(now, end)
        self.items.add(item)
        self._routine.replace_from(now, _without_overlap([item, *later]))
        self._decomposer.invalidate(since=now)
        name = self._persona.display_name
        self._writer.store(
            f"{josa(name, '은', '는')} {josa(digest, '을', '를')} 보고 "
            f"{reaction.description}하기로 했다",
            now,
            "plan",
        )

    def _replan(
        self,
        now: datetime.datetime,
        item: DayPlanItem,
        make_request: Callable[[], DayPlanBroadStrokesRequest],
    ) -> list[DayPlanItem] | None:
        """반응이 끝난 뒤의 계획. 실패하거나 비면 None."""
        request = make_request()
        request = replace(
            request,
            persona_background=f"{request.persona_background} "
            + self._replan_note(now, item),
        )
        try:
            made = self._planner.generate_day_plan(request)
        except _RECOVERABLE:
            return None
        later: list[DayPlanItem] = []
        for planned in made:
            start = max(planned.start_time.replace(tzinfo=None), item.end_time)
            stop = planned.end_time.replace(tzinfo=None)
            if stop > start:
                later.append(replace(planned, start_time=start, end_time=stop))
        return later or None

    def _replan_note(self, now: datetime.datetime, item: DayPlanItem) -> str:
        done = [
            f"{s.start:%H:%M}-{min(s.end, now):%H:%M} "
            f"{place_name(s.location_path)}: {s.description}"
            for s in self._routine.slots(now.date())
            if s.start < now
        ]
        note = (
            f"지금({format_time(now)})부터 남은 하루 계획만 다시 세운다. "
            f"방금 이렇게 하기로 했다: {item.action_content} "
            f"({place_name(item.location)}, {format_time(item.end_time)}까지)."
        )
        return f"{note} 오늘 지금까지의 계획: {'; '.join(done) or '(없음)'}"

    def _trimmed_rest(
        self, now: datetime.datetime, end: datetime.datetime
    ) -> list[DayPlanItem]:
        """재계획이 실패했을 때: 기존 계획에서 반응 구간과 겹치는 부분만 잘라 낸다."""
        rest: list[DayPlanItem] = []
        for slot in self._routine.slots(now.date()):
            old = self._routine.item_for(slot)
            if old is None or slot.end <= end:
                continue
            trimmed = replace(old, start_time=max(slot.start, end), end_time=slot.end)
            if old in self.items:
                self.items.add(trimmed)
            rest.append(trimmed)
        return rest


def _without_overlap(items: Sequence[DayPlanItem]) -> list[DayPlanItem]:
    """시작 순으로 늘어놓고 앞 항목 끝까지 시작을 미뤄 겹침을 없앤다. 길이가 0 이하면 버린다."""
    ordered: list[DayPlanItem] = []
    cursor: datetime.datetime | None = None
    for planned in sorted(items, key=lambda i: i.start_time):
        start = (
            planned.start_time if cursor is None else max(cursor, planned.start_time)
        )
        if planned.end_time <= start:
            continue
        ordered.append(replace(planned, start_time=start))
        cursor = planned.end_time if cursor is None else max(cursor, planned.end_time)
    return ordered


def parse_verdict(raw: str) -> Verdict:
    """응답을 판정으로. 깨졌거나 반응 내용이 비면 반응 없음."""
    data = _load(raw)
    if data is None:
        return Verdict(False, "", None)
    reason = _text(data, "reason")
    body = data.get("reaction")
    if data.get("react") is not True or not isinstance(body, dict):
        return Verdict(False, reason, None)
    fields = cast(dict[str, object], body)
    description = _text(fields, "description")
    if not description:
        return Verdict(False, reason, None)
    count = _minutes(fields.get("minutes"))
    return Verdict(
        True, reason, Reaction(description, _text(fields, "location"), count)
    )


def _minutes(value: object) -> int:
    """정수·실수(반올림)·숫자 문자열을 분으로. 못 읽으면 0(최소 분으로 보정된다)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    try:
        number = float(value)
    except ValueError:
        return 0
    return round(number) if math.isfinite(number) else 0


def _digest(seen: Sequence[Observation]) -> str:
    text = "; ".join(o.text.strip() for o in seen)
    return text if len(text) <= SUMMARY_MAX_CHARS else text[:SUMMARY_MAX_CHARS] + "…"


def _load(raw: str) -> dict[str, object] | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = cast(object, json.loads(raw[start : end + 1]))
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], data) if isinstance(data, dict) else None


def _text(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""
