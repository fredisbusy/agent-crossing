"""대사 템플릿: 화행 종류 x 말투별 한국어 문장을 주입된 rng로 고른다.

`unknown`은 모르는 주제를 물었을 때의 `smalltalk` 문장이다.
문장에는 마음 종류를 암시하는 단어를 쓰지 않는다 (SPEC §12 불가지 원칙).
`greet_again`은 오랜만에 만난 상대 인사, `thanks`는 선물을 받았을 때의 말이다.
채움 필드: {topic} {fact} {event} {day} {time} {place} {item}
"""

import datetime
import random
from collections.abc import Collection

from minds.social import format_day, format_time, place_name
from world.contracts import LocationPath

from .config import Tone

_TEMPLATES: dict[tuple[str, Tone], tuple[str, ...]] = {
    ("greet", "polite"): (
        "안녕하세요, 좋은 하루예요.",
        "안녕하세요! 또 뵙네요.",
        "어서 오세요, 반갑습니다.",
    ),
    ("greet", "casual"): ("안녕!", "어, 안녕! 반가워.", "여어, 잘 지내?"),
    ("greet_again", "polite"): (
        "오랜만이에요! 잘 지내셨어요?",
        "어머, 정말 오랜만이네요.",
    ),
    ("greet_again", "casual"): ("오랜만이다! 잘 지냈어?", "와, 이게 얼마 만이야!"),
    ("smalltalk", "polite"): (
        "오늘 날씨가 참 좋네요.",
        "요즘 마을이 활기차 보여요.",
        "바쁘게 지내다 보니 하루가 금방 가네요.",
        "요즘은 어떻게 지내세요?",
        "이 근처는 언제 와도 편안하네요.",
        "오늘은 뭐 하면서 보내실 거예요?",
    ),
    ("smalltalk", "casual"): (
        "오늘 날씨 진짜 좋다.",
        "요즘 마을이 북적북적하더라.",
        "하루가 왜 이렇게 빨리 가지?",
        "요즘 뭐 하고 지내?",
        "여기 오면 괜히 기분이 좋아.",
        "오늘 뭐 할 거야?",
    ),
    ("share_fact", "polite"): (
        "{topic} 얘기 들으셨어요? {fact}",
        "참, {topic}에 관해서 들은 게 있어요. {fact}",
        "{topic}, 알고 계세요? {fact}",
    ),
    ("share_fact", "casual"): (
        "{topic} 얘기 들었어? {fact}",
        "아, {topic} 말이야, {fact}",
        "있잖아, {topic}에 대해서 들었는데 {fact}",
    ),
    ("ask", "polite"): ("{topic}에 대해 아시는 게 있나요?",),
    ("ask", "casual"): ("{topic}에 대해 아는 거 있어?",),
    ("unknown", "polite"): (
        "{topic}은 잘 모르겠네요.",
        "글쎄요, {topic}은 저도 들은 적이 없어요.",
    ),
    ("unknown", "casual"): ("{topic}? 잘 모르겠네.", "글쎄, {topic}은 못 들었어."),
    ("invite", "polite"): (
        "{day} {time}에 {place}에서 {event} 어떠세요?",
        "{day} {time}에 {place}에서 {event}을(를) 해요. 꼭 와 주세요!",
    ),
    ("invite", "casual"): (
        "{day} {time}에 {place}에서 {event} 어때?",
        "{day} {time}에 {place}에서 {event} 하는데 같이 가자!",
    ),
    ("accept", "polite"): (
        "좋아요, {time}에 {place}에서 뵙겠습니다.",
        "네, {event} 꼭 갈게요. {time}에 봬요.",
        "초대해 주셔서 고마워요. {day} {time}에 갈게요.",
    ),
    ("accept", "casual"): (
        "좋아, {time}에 {place}에서 보자!",
        "응, {event} 갈게. {time}에 봐.",
        "불러 줘서 고마워! {day} {time}에 갈게.",
    ),
    ("decline", "polite"): (
        "아쉽지만 그 시간엔 어려워요.",
        "죄송해요, 이번엔 함께하기 힘들 것 같아요.",
    ),
    ("decline", "casual"): ("아쉽다, 그땐 좀 힘들어.", "미안, 이번엔 못 갈 것 같아."),
    ("gift", "polite"): (
        "{item} 준비했어요. 받아 주세요!",
        "작은 {item}이에요. 마음만 받아 주세요.",
    ),
    ("gift", "casual"): ("{item} 줄게! 받아 줘.", "이거 {item}이야. 너 주려고 챙겼어."),
    ("thanks", "polite"): (
        "어머, 고마워요! 소중히 할게요.",
        "이런 걸 다 챙겨 주시다니, 감사해요.",
    ),
    ("thanks", "casual"): ("와, 고마워! 진짜 기쁘다.", "헉, 나 주는 거야? 고마워!"),
    ("farewell", "polite"): ("그럼 이만 가볼게요. 안녕히 계세요.", "다음에 또 뵈어요."),
    ("farewell", "casual"): ("그럼 나 갈게, 잘 가!", "다음에 또 보자."),
}


def render(
    key: str,
    tone: Tone,
    rng: random.Random,
    *,
    now: datetime.datetime,
    topic: str = "",
    fact: str = "",
    event: str = "",
    when: datetime.datetime | None = None,
    location_path: LocationPath | None = None,
    item: str = "",
    avoid: Collection[str] = (),
) -> str:
    """템플릿 하나를 rng로 골라 필드를 채운다. `key`는 화행 종류 또는 위 특수 키.

    `avoid`에 있는 문장(최근에 한 말)은 다른 후보가 있으면 고르지 않는다.
    """
    filled = [
        template.format(
            topic=topic,
            fact=fact,
            event=event,
            day=format_day(when, now) if when else "",
            time=format_time(when) if when else "",
            place=place_name(location_path) if location_path else "",
            item=item,
        )
        for template in _TEMPLATES[(key, tone)]
    ]
    fresh = [text for text in filled if text not in avoid] or filled
    return fresh[rng.randrange(len(fresh))]


def all_templates() -> tuple[str, ...]:
    """테스트용: 모든 템플릿 문장."""
    return tuple(t for options in _TEMPLATES.values() for t in options)
