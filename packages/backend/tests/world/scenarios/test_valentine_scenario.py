"""밸런타인 시나리오: 전원 규칙 마음과, 주최자만 LLM 마음으로 바꾼 하이브리드가 같은 규칙으로 돈다."""

import asyncio
import datetime
import json

from agents.memory.memory_object import MemoryObject
from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from llm.clients.types import LlmGenerateOptions
from minds.llm import LLMMind
from world.residents import (
    ResidentConfig,
    ResidentMindFactory,
    apply_mind_selection,
    llm_persona,
    load_resident_configs,
)
from world.scenarios import ScenarioReport, apply_scenario, load_scenario, run_scenario
from world.space import load_town_space

HOST = "isabella_rodriguez"
PARTY = "밸런타인데이 파티"


class InvitingClient:
    """꺼낼 초대가 있으면 초대하고, 없으면 작별한다. 먼저 말을 걸지는 않는다."""

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
    ) -> str:
        del system, options, format_json
        if '"converse"' in prompt:
            return json.dumps({"converse": False})
        if f"{PARTY}에 초대하기" in prompt:
            acts = [{"kind": "invite", "event": PARTY}]
            return json.dumps({"utterance": "내일 파티에 와 주세요!", "acts": acts})
        acts = [{"kind": "farewell"}]
        return json.dumps(
            {"utterance": "또 봬요!", "acts": acts, "end_conversation": True}
        )


class CafePlanner:
    def generate_day_plan(
        self, request: DayPlanBroadStrokesRequest
    ) -> list[DayPlanItem]:
        day = request.today_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            DayPlanItem(
                start_time=day.replace(hour=8),
                end_time=day.replace(hour=16),
                location="Hobbs Cafe Counter",
                action_content="커피를 내린다",
            )
        ]


class NoMemory:
    def remember(
        self, content: str, now: datetime.datetime, *, kind: str = "observation"
    ) -> int:
        del content, now, kind
        return 1

    def retrieve(
        self, query: str, now: datetime.datetime, top_k: int
    ) -> list[MemoryObject]:
        del query, now, top_k
        return []


class NoReflection:
    def record_observation_importance(self, importance: int) -> None:
        del importance

    def should_reflect(self) -> bool:
        return False

    def reflect(self, *, now: datetime.datetime) -> None:
        del now


class FakeLlmFactory:
    def __init__(self, places: tuple[str, ...]) -> None:
        self._places = places

    def build(self, config: ResidentConfig) -> LLMMind:
        return LLMMind(
            persona=llm_persona(config, self._places),
            client=InvitingClient(),
            planner=CafePlanner(),
            memory=NoMemory(),
            reflection=NoReflection(),
        )


def _run(agent_ids: list[str], *, minutes: int | None = None) -> ScenarioReport:
    scenario = load_scenario("valentine")
    if minutes is not None:
        scenario = scenario.model_copy(update={"minutes": minutes})
    configs = apply_scenario(
        apply_mind_selection(load_resident_configs(), agent_ids=agent_ids), scenario
    )
    space = load_town_space()
    factory = ResidentMindFactory(
        start_time=scenario.start_time,
        seed=0,
        llm_factory=FakeLlmFactory(space.location_paths()),
    )
    return asyncio.run(
        run_scenario(scenario, configs=configs, space=space, mind_factory=factory)
    )


def test_all_rule_minds_spread_the_party_and_show_up_deterministically() -> None:
    first = _run([])
    assert first == _run([])
    assert first.agent_ids == () and first.mind_calls.keys() == {"schedule"}
    assert first.diffusion_rate >= 0.5
    assert first.committed and set(first.attended) <= set(first.committed)
    assert first.attended


def test_llm_host_drives_the_same_party_through_shared_rules() -> None:
    report = _run([HOST])
    assert report.agent_ids == (HOST,)
    assert report.mind_calls.get("llm", 0) > 0
    assert report.knew_event and report.committed
    assert report.attended
