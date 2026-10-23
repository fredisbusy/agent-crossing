"""LLMMind 테스트용 가짜 부품. LLM·네트워크 없이 돈다."""

import datetime
import json
from collections.abc import Callable

import numpy as np

from agents.memory.memory_object import MemoryObject, NodeType
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from llm.clients.types import LlmGenerateOptions
from minds.llm import DayPlanner, LLMMind, LlmPersona
from world.contracts import (
    BodyState,
    Holiday,
    MindContext,
    ResidentPublicView,
    TilePosition,
)

HOME = "Smallville > Hobbs Cafe > Counter"
CAFE = "Smallville > Hobbs Cafe > Seating"
PARK = "Smallville > Johnson Park > Garden"
SQUARE = "Smallville > Town Square"
PLACES = (
    "Smallville > Hobbs Cafe",
    HOME,
    CAFE,
    "Smallville > Johnson Park",
    PARK,
    SQUARE,
)
DAY = datetime.datetime(2023, 2, 13)


class ScriptedClient:
    """프롬프트를 받아 정해진 JSON을 돌려 준다. 받은 프롬프트를 기록한다."""

    def __init__(self, reply: Callable[[str], object]) -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
    ) -> str:
        self.prompts.append(prompt)
        reply = self._reply(prompt)
        return (
            reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
        )


class FixedPlanner:
    """요청 날짜의 9~12시 공원 산책 하나를 계획한다. 시간·분 단위는 늘 실패한다(하루 계획 구간으로 대체)."""

    def __init__(self) -> None:
        self.requests: list[DayPlanBroadStrokesRequest] = []
        self.hourly_calls: list[tuple[datetime.datetime, DayPlanItem]] = []
        self.minute_calls: list[tuple[datetime.datetime, HourlyPlanItem]] = []

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        self.hourly_calls.append((current_time, day_plan_item))
        raise ValueError("no hourly plan")

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        self.minute_calls.append((current_time, hourly_plan_item))
        raise ValueError("no minute plan")

    def generate_day_plan(
        self, request: DayPlanBroadStrokesRequest
    ) -> list[DayPlanItem]:
        self.requests.append(request)
        day = request.today_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            DayPlanItem(
                start_time=day.replace(hour=9),
                end_time=day.replace(hour=12),
                location="Johnson Park Garden",
                action_content="공원을 산책한다",
            )
        ]


class ListMemory:
    def __init__(self) -> None:
        self.stored: list[tuple[str, str]] = []
        self.batches: list[list[str]] = []
        """remember_many 호출마다 넘어온 문장들."""
        self.queries: list[str] = []
        self.stored_at_query: list[int] = []

    def remember(
        self, content: str, now: datetime.datetime, *, kind: str = "observation"
    ) -> int:
        self.stored.append((kind, content))
        return 3

    def remember_many(self, items: list[tuple[str, datetime.datetime]]) -> list[int]:
        self.batches.append([text for text, _ in items])
        return [self.remember(text, now) for text, now in items]

    def retrieve(
        self, query: str, now: datetime.datetime, top_k: int
    ) -> list[MemoryObject]:
        self.queries.append(query)
        self.stored_at_query.append(len(self.stored))
        return [
            MemoryObject(
                id=i,
                node_type=NodeType.OBSERVATION,
                citations=None,
                content=content,
                created_at=now,
                last_accessed_at=now,
                importance=3,
                embedding=np.zeros(1),
            )
            for i, (_, content) in enumerate(self.stored[-top_k:])
        ]


class CountingReflection:
    def __init__(self) -> None:
        self.total = 0

    def record_observation_importance(self, importance: int) -> None:
        self.total += importance

    def should_reflect(self) -> bool:
        return False

    def reflect(self, *, now: datetime.datetime) -> None:
        return None


def make_mind(
    client: ScriptedClient,
    *,
    resident_id: str = "isabella",
    max_turns: int = 6,
    reflection: CountingReflection | None = None,
    planner: DayPlanner | None = None,
) -> tuple[LLMMind, ListMemory]:
    memory = ListMemory()
    persona = LlmPersona(
        resident_id=resident_id,
        display_name=resident_id.title(),
        age=34,
        identity=("Loves making people feel welcome.",),
        home=HOME,
        known_places=PLACES,
        seed_memories=("카페를 운영한다.",),
    )
    mind = LLMMind(
        persona=persona,
        client=client,
        planner=planner or FixedPlanner(),
        memory=memory,
        reflection=reflection or CountingReflection(),
        max_turns=max_turns,
    )
    return mind, memory


def ctx(
    resident_id: str,
    now: datetime.datetime,
    *,
    where: str = CAFE,
    nearby: tuple[ResidentPublicView, ...] = (),
    holidays: tuple[Holiday, ...] = (),
) -> MindContext:
    body = BodyState(
        resident_id=resident_id,
        display_name=resident_id.title(),
        tile=TilePosition(x=0, y=0),
        location_path=where,
    )
    return MindContext(now=now, self_state=body, nearby=nearby, holidays=holidays)


def view(resident_id: str, where: str = CAFE) -> ResidentPublicView:
    return ResidentPublicView(
        resident_id=resident_id, display_name=resident_id.title(), location_path=where
    )
