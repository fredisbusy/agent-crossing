"""LLM 응답을 화행으로. 파싱에 실패하면 `smalltalk` 하나로 대체한다 (SPEC §13).

행사가 담긴 화행은 이름만 믿고 시각·장소는 아는 행사에서 채운다(환각 방지).
"""

import datetime
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, get_args

from minds.social import event_act
from world.contracts import LocationPath, SocialEvent, SpeechAct, SpeechActKind

_KINDS: frozenset[str] = frozenset(get_args(SpeechActKind))
_EVENT_KINDS = frozenset({"invite", "accept", "decline"})


@dataclass(frozen=True)
class SpeechDraft:
    text: str
    acts: tuple[SpeechAct, ...]
    end: bool


@dataclass(frozen=True)
class ActResolver:
    """화행 필드를 마음이 아는 것으로 채우는 함수들."""

    known_event: Callable[[str], SocialEvent | None]
    resolve_place: Callable[[str], LocationPath]
    gift_item: str | None


def parse_speech(raw: str, resolver: ActResolver) -> SpeechDraft | None:
    """말할 내용이 없으면 None(대화를 끝낸다)."""
    payload = _load(raw)
    if payload is None:
        return None
    text = payload.get("utterance")
    if not isinstance(text, str) or not text.strip():
        return None
    acts: list[SpeechAct] = []
    raw_acts = payload.get("acts")
    if isinstance(raw_acts, list):
        for item in cast(list[object], raw_acts):
            if isinstance(item, dict):
                act = _act(cast(dict[str, object], item), resolver)
                if act is not None and all(a.kind != act.kind for a in acts):
                    acts.append(act)
    if not acts:
        acts.append(SpeechAct(kind="smalltalk"))
    end = payload.get("end_conversation") is True or any(
        a.kind == "farewell" for a in acts
    )
    if end and all(a.kind != "farewell" for a in acts):
        acts.append(SpeechAct(kind="farewell"))
    return SpeechDraft(text.strip(), tuple(acts), end)


def parse_encounter(raw: str) -> bool:
    payload = _load(raw)
    return payload is not None and payload.get("converse") is True


def _act(item: dict[str, object], resolver: ActResolver) -> SpeechAct | None:
    kind = _text(item, "kind")
    if kind not in _KINDS:
        return None
    event_name = _text(item, "event")
    known = resolver.known_event(event_name) if event_name else None
    if kind in _EVENT_KINDS:
        return _event_act(kind, event_name, known, item, resolver)
    if kind == "share_fact":
        if known is not None:
            fact = _text(item, "fact") or ""
            return event_act(
                "share_fact", known, topic=known.name, fact=fact or known.name
            )
        topic, fact = _text(item, "topic"), _text(item, "fact")
        return (
            SpeechAct(kind="share_fact", topic=topic, fact=fact)
            if topic and fact
            else None
        )
    if kind == "ask":
        topic = _text(item, "topic")
        return SpeechAct(kind="ask", topic=topic) if topic else None
    if kind == "gift":
        gift = _text(item, "item") or resolver.gift_item
        return SpeechAct(kind="gift", item=gift) if gift else None
    return SpeechAct(kind=cast(SpeechActKind, kind))


def _event_act(
    kind: str,
    event_name: str | None,
    known: SocialEvent | None,
    item: dict[str, object],
    resolver: ActResolver,
) -> SpeechAct | None:
    if known is not None:
        return event_act(cast(SpeechActKind, kind), known)
    if kind == "decline":
        return SpeechAct(kind="decline", event=event_name)
    start, place = _time(item), _text(item, "location")
    if kind == "invite" and event_name and start is not None and place:
        return SpeechAct(
            kind="invite",
            event=event_name,
            start_time=start,
            location_path=resolver.resolve_place(place),
        )
    return None


def _load(raw: str) -> dict[str, object] | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = cast(object, json.loads(raw[start : end + 1]))
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], data) if isinstance(data, dict) else None


def _text(item: dict[str, object], key: str) -> str | None:
    value = item.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _time(item: dict[str, object]) -> datetime.datetime | None:
    value = _text(item, "start_time")
    if value is None:
        return None
    try:
        return datetime.datetime.fromisoformat(value).replace(
            tzinfo=None, second=0, microsecond=0
        )
    except ValueError:
        return None
