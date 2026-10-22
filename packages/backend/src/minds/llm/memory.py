"""기억 스트림 어댑터: `MemoryManager`를 LLMMind의 `MemoryStore`로 감싼다 (SPEC §3~§4)."""

import datetime

from agents.memory.memory_manager import MemoryManager, ObservationContext, PlanContext
from agents.memory.memory_object import MemoryObject


class ManagedMemory:
    """중요도 채점·임베딩·검색 점수는 `MemoryManager`(SPEC §4 공식)에 맡긴다."""

    def __init__(
        self, manager: MemoryManager, *, agent_name: str, identity: list[str]
    ) -> None:
        self._manager = manager
        self._agent_name = agent_name
        self._identity = identity

    def remember(
        self, content: str, now: datetime.datetime, *, kind: str = "observation"
    ) -> int:
        if kind == "plan":
            memory = self._manager.create_plan(
                content=content,
                now=now,
                context=PlanContext(self._agent_name, self._identity),
            )
        else:
            memory = self._manager.create_observation_from_text(
                content=content,
                now=now,
                context=ObservationContext(self._agent_name, self._identity),
            )
        return memory.importance

    def retrieve(
        self, query: str, now: datetime.datetime, top_k: int
    ) -> list[MemoryObject]:
        if not self._manager.memory_stream.memories:
            return []
        return self._manager.get_retrieval_memories(
            query, current_time=now, top_k=top_k
        )
