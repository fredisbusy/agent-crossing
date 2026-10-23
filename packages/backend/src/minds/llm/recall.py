"""기억 쓰기: 저장하면서 얻은 중요도를 성찰 누적값에 더한다 (SPEC §3~§4, §6)."""

import datetime
import threading

from .contracts import MemoryStore, ReflectionRunner


class MemoryWriter:
    """`MemoryStore`에 쓰고 중요도를 `ReflectionRunner`에 알린다.

    내가 한 말은 `defer`로 대기 목록에 넣고, 다음 기억 쓰기(`store`·`store_many`·
    `flush`)에 합쳐 한 번에 저장한다. 말한 직후 임베딩·중요도 채점을 기다리지 않기
    위해서다. 기억 검색 전에는 `flush`로 비워 검색 결과가 즉시 저장했을 때와 같다.
    시뮬레이션이 끝날 때 남은 대기 발화는 저장되지 않을 수 있다.
    """

    def __init__(self, memory: MemoryStore, reflection: ReflectionRunner) -> None:
        self._memory = memory
        self._reflection = reflection
        self._pending: list[tuple[str, datetime.datetime]] = []
        self._lock = threading.Lock()

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    def defer(self, text: str, now: datetime.datetime) -> None:
        with self._lock:
            self._pending.append((text, now))

    def flush(self) -> None:
        """대기 중인 기억을 저장한다. 없으면 아무것도 하지 않는다."""
        self.store_many([])

    def _take(self) -> list[tuple[str, datetime.datetime]]:
        with self._lock:
            taken, self._pending = self._pending, []
        return taken

    def store(
        self, text: str, now: datetime.datetime, kind: str = "observation"
    ) -> None:
        self.flush()
        importance = self._memory.remember(text, now, kind=kind)
        self._reflection.record_observation_importance(importance)

    def store_many(self, items: list[tuple[str, datetime.datetime]]) -> None:
        """대기 중인 기억을 앞에 두고 여러 기억을 한 번에(임베딩 1회, 중요도 배치 1회) 저장한다."""
        items = [*self._take(), *items]
        if not items:
            return
        for importance in self._memory.remember_many(items):
            self._reflection.record_observation_importance(importance)
