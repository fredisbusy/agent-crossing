"""대사 템플릿: 화행 종류 x 말투별 한국어 문장을 주입된 rng로 고른다.

`share_event`는 행사 소문, `unknown`은 모르는 주제를 물었을 때의 `smalltalk` 문장이다.
주제가 낱말 하나가 아니면(구·절) 주제를 되받지 않는 `unknown_vague` 문장을 쓴다.
문장에는 마음 종류를 암시하는 단어를 쓰지 않는다 (SPEC §12 불가지 원칙).
`greet_again`은 오랜만에 만난 상대 인사, `thanks`는 선물을 받았을 때의 말이다.
채움 필드: {topic} {fact} {event} {day} {time} {place} {item}
`{fact}`에는 평서형 사실 문장을 말투에 맞는 전하는 말로 바꿔 넣는다(`relay`).
"""

import datetime
import random
import re
from collections.abc import Sequence

from minds.social import Voice, format_day, format_time, josa, place_name
from world.contracts import LocationPath

from .config import Tone
from .voices import VOICE_TEMPLATES

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
    ("share_event", "polite"): (
        "{event} 소식 들으셨어요? {day} {time}에 {place}에서 열린대요.",
        "참, {event} 말이에요. {day} {time}에 {place}에서 한대요.",
    ),
    ("share_event", "casual"): (
        "{event} 얘기 들었어? {day} {time}에 {place}에서 한대!",
        "있잖아, {day} {time}에 {place}에서 {event} 한대.",
    ),
    ("ask", "polite"): ("{topic}에 대해 아시는 게 있나요?",),
    ("ask", "casual"): ("{topic}에 대해 아는 거 있어?",),
    ("unknown", "polite"): (
        "{topic} 잘 모르겠네요.",
        "글쎄요, {topic} 저도 들은 적이 없어요.",
    ),
    ("unknown", "casual"): ("{topic} 잘 모르겠네.", "글쎄, {topic} 못 들었어."),
    ("unknown_vague", "polite"): (
        "글쎄요, 그건 잘 모르겠네요.",
        "음, 그 얘기는 저도 들은 적이 없어요.",
    ),
    ("unknown_vague", "casual"): ("글쎄, 그건 잘 모르겠네.", "음, 그 얘기는 못 들었어."),
    ("invite", "polite"): (
        "{day} {time}에 {place}에서 {event} 어떠세요?",
        "{day} {time}에 {place}에서 {event} 열어요. 꼭 와 주세요!",
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


_PLAIN_ENDING = re.compile(r"(이|아니)?다(?=\.(?:\s|$)|$)")
"""마침표나 글 끝 앞의 평서형 "-다". 앞의 "이·아니"는 "-래"로 바뀌므로 함께 잡는다."""
_FORMAL_ENDING = "니"
""""-ㅂ니다·습니다"의 "니". 이미 높임말이라 바꾸지 않는다."""


TOPIC_ECHO_MAX_CHARS = 8
"""모르는 주제를 되받아 말할 수 있는 길이. 이보다 길거나 띄어쓰기가 있으면 구·절로 본다."""


def _echoable(topic: str) -> bool:
    return 0 < len(topic) <= TOPIC_ECHO_MAX_CHARS and not any(c.isspace() for c in topic)


def relay(fact: str, tone: Tone) -> str:
    """평서형 사실 문장("…하고 있다.")을 전하는 말("…하고 있대요." / "…하고 있대.")로 바꾼다.

    "-이다·아니다"는 "-이래(요)·아니래(요)"로, 그 밖의 "-다"는 "-대(요)"로 바꾼다.
    "-다"로 끝나지 않는 문장(명사구, 이미 "-대요"·"-습니다"인 문장)은 그대로 둔다.
    """
    suffix = "요" if tone == "polite" else ""

    def swap(match: re.Match[str]) -> str:
        copula = match.group(1)
        if copula:
            return f"{copula}래{suffix}"
        if fact[: match.start()].endswith(_FORMAL_ENDING):
            return match.group(0)
        return f"대{suffix}"

    return _PLAIN_ENDING.sub(swap, fact.strip())


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
    avoid: Sequence[str] = (),
    voice: Voice | None = None,
) -> str:
    """템플릿 하나를 rng로 골라 필드를 채운다. `key`는 화행 종류 또는 위 특수 키.

    `avoid`(오래된 순서의 최근 대사)에 있는 문장은 다른 후보가 있으면 고르지 않고,
    모두 썼으면 가장 오래전에 한 말을 고른다.
    """
    topic = topic.strip()
    if key == "unknown":
        if _echoable(topic):
            topic = josa(topic, "은", "는")
        else:
            key = "unknown_vague"
    filled = [
        template.format(
            topic=topic,
            fact=relay(fact, tone),
            event=event,
            day=format_day(when, now) if when else "",
            time=format_time(when) if when else "",
            place=place_name(location_path) if location_path else "",
            item=item,
        )
        for template in _options(key, tone, voice)
    ]
    fresh = [text for text in filled if text not in avoid]
    if fresh:
        return fresh[rng.randrange(len(fresh))]
    order = list(avoid)
    return min(filled, key=lambda text: order.index(text) if text in order else -1)


def _options(key: str, tone: Tone, voice: Voice | None) -> tuple[str, ...]:
    """말투 템플릿을 앞세운다. 말투 문장이 하나뿐이면 존댓말·반말 템플릿을 섞어 되풀이를 줄인다."""
    base = _TEMPLATES[(key, tone)]
    voiced = VOICE_TEMPLATES.get((key, voice), ()) if voice is not None else ()
    if len(voiced) >= 2:
        return voiced
    return (*voiced, *base)


def all_templates() -> tuple[str, ...]:
    """테스트용: 모든 템플릿 문장."""
    pools = (*_TEMPLATES.values(), *VOICE_TEMPLATES.values())
    return tuple(t for options in pools for t in options)
