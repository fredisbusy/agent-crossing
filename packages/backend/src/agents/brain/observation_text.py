"""기억 스트림에 저장·임베딩되는 자연어 관찰 문장을 만든다.

시각·성격·계획 같은 메타데이터는 넣지 않는다(시각은 MemoryObject.created_at,
나머지는 프롬프트의 별도 필드가 담당). 같은 상황이면 같은 문자열을 돌려준다.
"""

from typing import Literal

_TEMPLATES: dict[str, dict[str, str]] = {
    "ko": {
        "unknown": "알 수 없는 장소",
        "at": "{name}이(가) {place}에 있다.",
        "nearby": "주변: {items}.",
        "events": "사건: {items}.",
    },
    "en": {
        "unknown": "an unknown place",
        "at": "{name} is at {place}.",
        "nearby": "Nearby: {items}.",
        "events": "Events: {items}.",
    },
}
UNKNOWN_LOCATION = _TEMPLATES["ko"]["unknown"]


def build_observation_text(
    *,
    agent_name: str,
    location: str | None,
    observed_entities: list[str] | None,
    observed_events: list[str] | None,
    language: Literal["ko", "en"] = "ko",
) -> str:
    """장소·주변 엔티티·사건 중심의 관찰 문장을 만든다."""
    template = _TEMPLATES[language]
    place = (location or "").strip()
    if not place or place == "unknown":
        place = template["unknown"]
    sentences = [template["at"].format(name=agent_name, place=place)]
    if observed_entities:
        sentences.append(template["nearby"].format(items=", ".join(observed_entities)))
    if observed_events:
        sentences.append(template["events"].format(items="; ".join(observed_events)))
    return " ".join(sentences)
