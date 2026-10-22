"""LLMMind가 주입받는 의존성 계약. 실제 구현은 `agents`·`llm`에 있다."""

import datetime
from dataclasses import dataclass
from typing import Protocol

from agents.memory.memory_object import MemoryObject
from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from llm.clients.types import LlmGenerateOptions
from world.contracts import LocationPath, ResidentId


@dataclass(frozen=True)
class LlmPersona:
    """LLM 마음 한 명의 정체성과 아는 장소 (SPEC §5 Persona, §15 개인 환경 트리)."""

    resident_id: ResidentId
    display_name: str
    age: int
    identity: tuple[str, ...]
    """정체성 문장."""
    home: LocationPath
    known_places: tuple[LocationPath, ...]
    seed_memories: tuple[str, ...] = ()


class GenerateClient(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
    ) -> str: ...


class DayPlanner(Protocol):
    def generate_day_plan(
        self, request: DayPlanBroadStrokesRequest
    ) -> list[DayPlanItem]: ...


class MemoryStore(Protocol):
    """기억 스트림 (SPEC §3~§4). `agents.memory.MemoryManager`가 따른다."""

    def remember(
        self, content: str, now: datetime.datetime, *, kind: str = "observation"
    ) -> int:
        """기억을 저장하고 매긴 중요도를 돌려 준다. kind: observation | plan."""
        ...

    def retrieve(
        self, query: str, now: datetime.datetime, top_k: int
    ) -> list[MemoryObject]: ...


class ReflectionRunner(Protocol):
    def record_observation_importance(self, importance: int) -> None: ...

    def should_reflect(self) -> bool: ...

    def reflect(self, *, now: datetime.datetime) -> None: ...
