"""기억 쓰기: 저장하면서 얻은 중요도를 성찰 누적값에 더한다 (SPEC §3~§4, §6)."""

import datetime

from .contracts import MemoryStore, ReflectionRunner


class MemoryWriter:
    """`MemoryStore`에 쓰고 중요도를 `ReflectionRunner`에 알린다."""

    def __init__(self, memory: MemoryStore, reflection: ReflectionRunner) -> None:
        self._memory = memory
        self._reflection = reflection

    def store(
        self, text: str, now: datetime.datetime, kind: str = "observation"
    ) -> None:
        importance = self._memory.remember(text, now, kind=kind)
        self._reflection.record_observation_importance(importance)

    def store_many(self, items: list[tuple[str, datetime.datetime]]) -> None:
        """여러 기억을 한 번에(임베딩 1회, 중요도 배치 1회) 저장한다."""
        if not items:
            return
        for importance in self._memory.remember_many(items):
            self._reflection.record_observation_importance(importance)
