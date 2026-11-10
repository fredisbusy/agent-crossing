"""대화가 끝난 뒤의 정리: 메모는 기억으로, 계획 메모는 다음 계획 요청으로 (TODO 3-C, SPEC §7).

대화마다 LLM 1회로 `{"memo", "plan_note"}`를 받는다. 메모는 관찰 기억, 계획 메모는
plan 기억으로 남기고, 계획 메모는 `PLAN_NOTE_LIFETIME` 동안 하루 계획·재계획 요청의
배경에 싣는다. 대화 직후에 하루를 다시 짜지는 않는다(연속 재계획 방지, SPEC §7).
"""

import datetime
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from llm.clients.types import LlmGenerateOptions
from llm.template_loader import render_template
from minds.social import Slot, format_time, josa, place_name
from world.contracts import ConversationView, ResidentId, Utterance

from ..contracts import GenerateClient, LlmPersona
from ..prompts import persona_text
from ..recall import MemoryWriter

NOTES_OPTIONS = LlmGenerateOptions(temperature=0.3, top_p=0.9, num_predict=256)
MIN_TRANSCRIPT_LINES = 2
"""이보다 짧은 대화(말 한 마디)는 정리하지 않는다."""
PLAN_NOTE_LIFETIME = datetime.timedelta(hours=24)
"""계획 메모를 계획 요청에 싣는 기간(게임 시간)."""
MAX_PLAN_NOTES = 5
"""계획 요청에 싣는 계획 메모 수 상한(최근 것부터)."""
_NO_PLAN = "- (남은 계획 없음)"


@dataclass
class _Talk:
    conversation_id: str
    partner_id: ResidentId
    partner_name: str
    lines: list[str] = field(default_factory=list)
    seen: set[tuple[ResidentId, datetime.datetime, str]] = field(default_factory=set)
    """대화 기록에 이미 들어간 발화(화자, 시각, 문장)."""


class ConversationNotes:
    def __init__(
        self, *, persona: LlmPersona, client: GenerateClient, writer: MemoryWriter
    ) -> None:
        self._persona = persona
        self._client = client
        self._writer = writer
        self._talk: _Talk | None = None
        self._plan_notes: list[tuple[datetime.datetime, str]] = []

    def track(
        self,
        conversation: ConversationView,
        partner_id: ResidentId,
        names: Mapping[ResidentId, str],
        own: Utterance | None = None,
    ) -> None:
        """내 차례마다 지금까지의 대화(내가 방금 한 말 포함)를 받아 둔다."""
        said = [*conversation.history, *([own] if own is not None else [])]
        self._talk = _Talk(
            conversation_id=conversation.conversation_id,
            partner_id=partner_id,
            partner_name=names.get(partner_id, partner_id),
            lines=[f"{names.get(u.speaker_id, u.speaker_id)}: {u.text}" for u in said],
            seen={(u.speaker_id, u.spoken_at, u.text) for u in said},
        )

    def heard(self, utterance: Utterance) -> None:
        """내 마지막 차례 뒤에 상대가 한 말(작별 등)을 덧붙인다."""
        talk = self._talk
        if talk is None or utterance.speaker_id != talk.partner_id:
            return
        key = (utterance.speaker_id, utterance.spoken_at, utterance.text)
        if key not in talk.seen:
            talk.seen.add(key)
            talk.lines.append(f"{talk.partner_name}: {utterance.text}")

    def digest(
        self,
        now: datetime.datetime,
        *,
        current_conversation_id: str | None,
        summary: str,
        remaining: Sequence[Slot],
        events: Sequence[str] = (),
    ) -> None:
        """끝난 대화가 있으면 한 번 정리한다. 대화 중이거나 정리할 게 없으면 아무것도 하지 않는다."""
        talk = self._talk
        if talk is None or talk.conversation_id == current_conversation_id:
            return
        self._talk = None
        if len(talk.lines) < MIN_TRANSCRIPT_LINES:
            return
        memo, plan_note = self._ask(talk, now, summary, remaining, events)
        name = self._persona.display_name
        if memo:
            self._writer.store(f"{name}의 {talk.partner_name}와의 대화 메모: {memo}", now)
        if plan_note:
            partner = josa(talk.partner_name, "과", "와")
            self._writer.store(
                f"{josa(name, '은', '는')} {partner} 이야기한 뒤 이렇게 하기로 했다: {plan_note}",
                now,
                "plan",
            )
            self._plan_notes.append((now, f"{partner} 이야기한 뒤: {plan_note}"))

    def plan_lines(self, now: datetime.datetime) -> list[str]:
        """계획 요청 배경에 실을 최근 계획 메모. 기간이 지난 메모는 버린다."""
        self._plan_notes = [
            (at, note) for at, note in self._plan_notes if now - at < PLAN_NOTE_LIFETIME
        ]
        return [note for _, note in self._plan_notes[-MAX_PLAN_NOTES:]]

    def _ask(
        self,
        talk: _Talk,
        now: datetime.datetime,
        summary: str,
        remaining: Sequence[Slot],
        events: Sequence[str],
    ) -> tuple[str, str]:
        """`events`는 이미 잡힌 약속·아는 행사 줄. 모델이 같은 약속을 새 계획으로 다시 내지 않게 싣는다."""
        plans = "\n".join(
            [
                *(
                    f"- {format_time(s.start)}~{format_time(s.end)} "
                    f"{place_name(s.location_path)}: {s.description}"
                    for s in remaining
                ),
                *(f"- {line}" for line in events),
            ]
        )
        prompt = render_template(
            "town_talk_notes.md",
            persona=persona_text(self._persona, summary),
            name=self._persona.display_name,
            now=f"{now.month}월 {now.day}일 {format_time(now)}",
            plans=plans or _NO_PLAN,
            partner=talk.partner_name,
            history="\n".join(f"- {line}" for line in talk.lines),
        )
        try:
            raw = self._client.generate(
                prompt=prompt, options=NOTES_OPTIONS, format_json=True
            )
        except (RuntimeError, TimeoutError, ValueError):
            return "", ""
        return parse_notes(raw)


def parse_notes(raw: str) -> tuple[str, str]:
    """(메모, 계획 메모). 형식이 틀리거나 값이 없으면 빈 문자열."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return "", ""
    try:
        data = cast(object, json.loads(raw[start : end + 1]))
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    payload = cast(dict[str, object], data)
    memo, plan_note = payload.get("memo"), payload.get("plan_note")
    return (
        memo.strip() if isinstance(memo, str) else "",
        plan_note.strip() if isinstance(plan_note, str) else "",
    )
