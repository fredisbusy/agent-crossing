"""반응 결정을 plan 기억 한 문장으로 만든다 (SPEC §7).

관찰 문장 목록을 그대로 붙이지 않고 본 대상(주민 이름)만 싣는다. 관찰 자체는 이미
기억 스트림에 따로 저장돼 있다.
"""

from collections.abc import Mapping, Sequence

from minds.social import josa
from world.contracts import Observation, ResidentId

QUOTED_MAX_CHARS = 60
"""대상이 없는 관찰(사건)을 인용할 때의 최대 길이."""
_TRAILING = " .!?。"


def decision_memory(
    name: str,
    seen: Sequence[Observation],
    names: Mapping[ResidentId, str],
    description: str,
) -> str:
    """`<이름>은/는 <본 것>을/를 보고 이렇게 하기로 했다: <행동>`.

    행동 문장은 LLM이 쓴 그대로 두고(활용을 바꾸지 않는다) 끝 문장부호만 뗀다.
    """
    decided = description.strip().rstrip(_TRAILING)
    return (
        f"{josa(name, '은', '는')} {josa(_seen_phrase(seen, names), '을', '를')} 보고 "
        f"이렇게 하기로 했다: {decided}"
    )


def _seen_phrase(seen: Sequence[Observation], names: Mapping[ResidentId, str]) -> str:
    who: list[str] = []
    for observation in seen:
        subject = observation.subject_id
        if subject is None:
            continue
        label = names.get(subject) or subject.replace("_", " ").title()
        if label not in who:
            who.append(label)
    if who:
        return ", ".join(who)
    text = seen[0].text.strip().rstrip(_TRAILING) if seen else ""
    if not text:
        return "주변"
    if len(text) > QUOTED_MAX_CHARS:
        text = text[:QUOTED_MAX_CHARS] + "…"
    return f"'{text}'"
