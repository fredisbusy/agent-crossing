"""사실 저장소: 들은 사실을 주제별 최신 값으로 보관하고 전달 이력을 관리한다.

행사 소문이면 `event`가 붙는다. 행사의 주제는 행사 이름이다.
"""

import datetime
from dataclasses import dataclass

from world.contracts import ResidentId, SocialEvent


@dataclass(frozen=True)
class Fact:
    topic: str
    fact: str
    source_resident_id: ResidentId
    learned_at: datetime.datetime
    event: SocialEvent | None = None


class FactStore:
    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._told: set[tuple[ResidentId, str, str]] = set()

    def learn(
        self,
        topic: str,
        fact: str,
        source_resident_id: ResidentId,
        learned_at: datetime.datetime,
        event: SocialEvent | None = None,
    ) -> Fact:
        """같은 topic은 최신 값으로 갱신한다. 행사 정보는 새 값에 없으면 이전 것을 지킨다."""
        previous = self._facts.get(topic)
        if event is None and previous is not None:
            event = previous.event
        stored = Fact(topic, fact, source_resident_id, learned_at, event)
        self._facts[topic] = stored
        return stored

    def get(self, topic: str) -> Fact | None:
        return self._facts.get(topic)

    def all(self) -> tuple[Fact, ...]:
        return tuple(
            sorted(self._facts.values(), key=lambda f: (f.learned_at, f.topic))
        )

    def events(self, now: datetime.datetime) -> tuple[SocialEvent, ...]:
        """알고 있는, 아직 끝나지 않은 행사."""
        return tuple(
            f.event
            for f in self.all()
            if f.event is not None and f.event.end_time > now
        )

    def unshared_for(self, other: ResidentId) -> tuple[Fact, ...]:
        """아직 `other`에게 전하지 않았고 `other`에게서 듣지도 않은 사실."""
        return tuple(
            f
            for f in self.all()
            if f.source_resident_id != other and _told_key(other, f) not in self._told
        )

    def mark_told(self, other: ResidentId, fact: Fact) -> None:
        self._told.add(_told_key(other, fact))

    def was_told(self, other: ResidentId, topic: str) -> bool:
        """그 주제의 현재 내용을 `other`에게 이미 전했거나 `other`에게서 들었으면 True."""
        known = self._facts.get(topic)
        if known is None:
            return False
        return (
            known.source_resident_id == other or _told_key(other, known) in self._told
        )

    def mark_topic_told(self, other: ResidentId, topic: str) -> None:
        """그 주제의 현재 내용을 `other`에게 전한 것으로 친다."""
        known = self._facts.get(topic)
        if known is not None:
            self.mark_told(other, known)


def _told_key(other: ResidentId, fact: Fact) -> tuple[ResidentId, str, str]:
    """행사 소문은 주제만으로, 일반 사실은 내용까지 같아야 이미 전한 것으로 본다.

    행사 문장의 "오늘·내일"은 말할 때마다 달라지므로 문장으로 비교하지 않는다.
    """
    return (other, fact.topic, "" if fact.event is not None else fact.fact)
