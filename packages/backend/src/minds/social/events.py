"""행사·시각·장소를 문장과 화행으로 옮기는 공유 표현 (SPEC §13).

두 마음이 같은 문장 형식을 쓰도록 여기에만 둔다 (불가지 원칙).
"""

import datetime

from world.contracts import ResidentId, SocialEvent, SpeechAct, SpeechActKind

from .places import place_name

DEFAULT_EVENT_DURATION = datetime.timedelta(minutes=60)
"""화행에 종료 시각이 없을 때 쓰는 기본 행사 길이 (SPEC §13)."""


def format_time(moment: datetime.datetime) -> str:
    meridiem = "오전" if moment.hour < 12 else "오후"
    hour = moment.hour % 12 or 12
    if moment.minute:
        return f"{meridiem} {hour}시 {moment.minute}분"
    return f"{meridiem} {hour}시"


def format_day(moment: datetime.datetime, now: datetime.datetime) -> str:
    """오늘·내일이면 그 말로, 아니면 `2월 14일`."""
    days = (moment.date() - now.date()).days
    if days == 0:
        return "오늘"
    if days == 1:
        return "내일"
    return f"{moment.month}월 {moment.day}일"


ROMAN_FINAL_ENDINGS = ("l", "m", "n", "ng")
"""로마자 이름이 이 글자로 끝나면 받침이 있다고 본다(Lin→린, Sam→샘, Hill→힐)."""
ROMAN_STOP_FINALS = "bkp"
"""모음(또는 ck의 c) 바로 뒤에서 끝나면 받침으로 읽는 글자(Jack→잭, Bob→밥, Philip→필립)."""
_ROMAN_VOWELS = "aeiouy"
_DIGITS_WITH_FINAL = "013678"
"""영·일·삼·육·칠·팔."""


def has_final(word: str) -> bool:
    """마지막 글자를 한국어로 읽을 때 받침이 있으면 True.

    한글은 종성으로 판정한다. 로마자는 한글 표기 관행을 따른 어림 규칙이다: l·m·n·ng로
    끝나거나 모음 뒤 b·k·p(ck 포함)로 끝나면 받침이 있고, 나머지(모음, s·z·r·t·d 등은
    보통 "스·즈·르·트·드"로 풀어 적는다)는 받침이 없다. 숫자는 읽는 소리로 판정한다.
    """
    text = word.rstrip(" .,!?…\"')")
    if not text:
        return False
    last = text[-1]
    if "가" <= last <= "힣":
        return (ord(last) - ord("가")) % 28 != 0
    if last.isdigit():
        return last in _DIGITS_WITH_FINAL
    lower = text.lower()
    if lower.endswith(ROMAN_FINAL_ENDINGS):
        return True
    if len(lower) >= 2 and lower[-1] in ROMAN_STOP_FINALS:
        return lower[-2] in _ROMAN_VOWELS or lower.endswith("ck")
    return False


def josa(word: str, with_final: str, without_final: str) -> str:
    """받침 유무에 맞는 조사를 붙인다. 판정은 `has_final`(로마자 이름 포함)을 따른다."""
    return word + (with_final if has_final(word) else without_final)


def describe_event(event: SocialEvent, now: datetime.datetime) -> str:
    """행사를 한 문장으로. 사실 저장소의 내용과 기억 문장에 같이 쓴다."""
    return (
        f"{format_day(event.start_time, now)} {format_time(event.start_time)}부터 "
        f"{format_time(event.end_time)}까지 {place_name(event.location_path)}에서 "
        f"{josa(event.name, '이', '가')} 열린다."
    )


def event_from_act(act: SpeechAct, speaker_id: ResidentId | None) -> SocialEvent | None:
    """행사 필드가 다 있는 화행이면 행사로. 주최자가 없는 초대는 초대한 사람을 주최자로 본다."""
    if not act.event or act.start_time is None or act.location_path is None:
        return None
    end = act.end_time or act.start_time + DEFAULT_EVENT_DURATION
    if end <= act.start_time:
        end = act.start_time + DEFAULT_EVENT_DURATION
    host = act.host_id or (speaker_id if act.kind == "invite" else None)
    return SocialEvent(
        name=act.event,
        start_time=act.start_time,
        end_time=end,
        location_path=act.location_path,
        host_id=host,
    )


def event_act(kind: SpeechActKind, event: SocialEvent, **extra: str) -> SpeechAct:
    """행사를 실은 화행(`invite`·`accept`·`share_fact` 등)."""
    return SpeechAct(
        kind=kind,
        event=event.name,
        start_time=event.start_time,
        end_time=event.end_time,
        location_path=event.location_path,
        host_id=event.host_id,
        **extra,
    )
