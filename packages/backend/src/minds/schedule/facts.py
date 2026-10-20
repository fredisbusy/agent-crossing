"""사실 저장소: 들은 사실을 주제별 최신 값으로 보관하고 전달 이력을 관리한다."""

import datetime
from dataclasses import dataclass

from world.contracts import ResidentId


@dataclass(frozen=True)
class Fact:
    topic: str
    fact: str
    source_resident_id: ResidentId
    learned_at: datetime.datetime


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
    ) -> None:
        """같은 topic은 최신 값으로 갱신한다."""
        self._facts[topic] = Fact(topic, fact, source_resident_id, learned_at)

    def get(self, topic: str) -> Fact | None:
        return self._facts.get(topic)

    def all(self) -> tuple[Fact, ...]:
        return tuple(
            sorted(self._facts.values(), key=lambda f: (f.learned_at, f.topic))
        )

    def unshared_for(self, other: ResidentId) -> tuple[Fact, ...]:
        """아직 `other`에게 전하지 않았고 `other`에게서 듣지도 않은 사실."""
        return tuple(
            f
            for f in self.all()
            if f.source_resident_id != other
            and (other, f.topic, f.fact) not in self._told
        )

    def mark_told(self, other: ResidentId, fact: Fact) -> None:
        self._told.add((other, fact.topic, fact.fact))
