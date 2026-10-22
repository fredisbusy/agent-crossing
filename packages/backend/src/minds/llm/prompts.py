"""마을 대화·조우 프롬프트 (SPEC §5: Persona, Current Plan, Retrieved Memories, Spatial Context)."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass

from agents.memory.memory_object import MemoryObject
from llm.template_loader import render_template
from minds.social import describe_event, format_day, format_time, place_name
from world.contracts import Holiday, SocialEvent, SpeechAct

from .contracts import LlmPersona

SPEECH_JSON_SHAPE = (
    '{"utterance": "<string>", "acts": [{"kind": "<kind>", "event": "<선택>", '
    '"topic": "<선택>", "fact": "<선택>", "item": "<선택>", '
    '"start_time": "<선택>", "location": "<선택>"}], "end_conversation": <boolean>}'
)
_NONE = "- (없음)"


@dataclass(frozen=True)
class Scene:
    """프롬프트 공통 장면: 지금 시각·장소·하던 일·기념일·상대와의 관계·기억."""

    now: datetime.datetime
    place: str
    activity: str
    holidays: Sequence[Holiday]
    partner: str
    friendship: int
    last_met: datetime.datetime | None
    memories: Sequence[MemoryObject]


def build_speech_prompt(
    persona: LlmPersona,
    scene: Scene,
    *,
    events: Sequence[str],
    partner_notes: Sequence[str],
    talking_points: Sequence[str],
    history: Sequence[str],
    must_end: bool,
) -> str:
    turn_note = "이번 말로 대화를 마무리한다." if must_end else ""
    return render_template(
        "town_speech.md",
        **_scene_vars(persona, scene),
        events=_bullets(events),
        partner_notes=_bullets(
            [n.format(partner=scene.partner) for n in partner_notes]
        ),
        talking_points=_bullets(talking_points),
        history=_bullets(history) if history else "- (아직 아무 말도 하지 않았다)",
        turn_note=turn_note,
        json_shape=SPEECH_JSON_SHAPE,
    )


def build_encounter_prompt(
    persona: LlmPersona,
    scene: Scene,
    *,
    partner_place: str,
    partner_activity: str,
) -> str:
    return render_template(
        "town_encounter.md",
        **_scene_vars(persona, scene),
        partner_place=place_name(partner_place),
        partner_activity=partner_activity,
    )


def describe_point(act: SpeechAct, now: datetime.datetime) -> str:
    """꺼낼 만한 화행을 사람이 읽는 문장으로."""
    if act.kind == "invite" and act.start_time is not None:
        when = f"{format_day(act.start_time, now)} {format_time(act.start_time)}"
        return f"{act.event}에 초대하기 ({when})"
    if act.kind == "gift":
        return f"{act.item} 선물하기"
    if act.kind == "share_fact":
        return f"소식 전하기: {act.fact}"
    return act.kind


def describe_events(
    hosting: Sequence[SocialEvent],
    attending: Sequence[SocialEvent],
    heard: Sequence[SocialEvent],
    now: datetime.datetime,
) -> list[str]:
    lines = [f"{e.name}: {describe_event(e, now)} (내가 연다)" for e in hosting]
    lines += [f"{e.name}: {describe_event(e, now)} (가기로 했다)" for e in attending]
    lines += [f"{e.name}: {describe_event(e, now)} (들은 소식)" for e in heard]
    return lines


def _scene_vars(persona: LlmPersona, scene: Scene) -> dict[str, str]:
    holidays = "\n".join(
        f"- 오늘은 {h.name}: {' '.join(h.customs)}".rstrip() for h in scene.holidays
    )
    last_met = ""
    if scene.last_met is not None:
        last_met = f"마지막 대화: {format_day(scene.last_met, scene.now)} {format_time(scene.last_met)}"
    return {
        "persona": _persona_text(persona),
        "name": persona.display_name,
        "now": f"{scene.now.month}월 {scene.now.day}일 {format_time(scene.now)}",
        "place": place_name(scene.place),
        "activity": scene.activity,
        "holidays": holidays,
        "partner": scene.partner,
        "friendship": str(scene.friendship),
        "last_met": last_met,
        "memories": _bullets([m.content for m in scene.memories]),
    }


def _persona_text(persona: LlmPersona) -> str:
    lines = [f"{persona.display_name} ({persona.age}세)"]
    lines += list(persona.identity)
    return "\n".join(lines)


def _bullets(lines: Sequence[str]) -> str:
    return "\n".join(f"- {line}" for line in lines) if lines else _NONE
