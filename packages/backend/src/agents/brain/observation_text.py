"""기억 스트림에 저장·임베딩되는 자연어 관찰 문장을 만든다.

시각·성격·계획 같은 메타데이터는 넣지 않는다(시각은 MemoryObject.created_at,
나머지는 프롬프트의 별도 필드가 담당). 같은 상황이면 같은 문자열을 돌려준다.
"""

UNKNOWN_LOCATION = "알 수 없는 장소"


def build_observation_text(
    *,
    agent_name: str,
    location: str | None,
    observed_entities: list[str],
    observed_events: list[str],
) -> str:
    """장소·주변 엔티티·사건 중심의 관찰 문장을 만든다."""
    place = (location or "").strip()
    if not place or place == "unknown":
        place = UNKNOWN_LOCATION
    sentences = [f"{agent_name}이(가) {place}에 있다."]
    if observed_entities:
        sentences.append(f"주변: {', '.join(observed_entities)}.")
    if observed_events:
        sentences.append(f"사건: {'; '.join(observed_events)}.")
    return " ".join(sentences)
