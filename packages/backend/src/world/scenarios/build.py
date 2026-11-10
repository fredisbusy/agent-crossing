"""마을 조립: 주민 설정 -> 마음 선택 -> 시나리오 -> 공간 -> 마음 공장 -> 시뮬레이션.

CLI(`run_town_scenario.py`)와 API(`TownRuntime`)가 같은 함수로 마을을 만든다.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from llm.clients.provider_factory import ProviderClient, build_provider_client
from settings import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_REASONING_EFFORT,
    LLM_TIMEOUT_SECONDS,
)
from world.contracts import Space
from world.residents import (
    LLMMindFactory,
    MindFactory,
    Resident,
    ResidentConfig,
    ResidentMindFactory,
    apply_mind_selection,
    load_resident_configs,
)
from world.space import load_town_space
from world.town import SimClock, TownSimulation

from .contracts import ScenarioConfig
from .loader import apply_scenario, focus_event
from .report import ScenarioTracker


@dataclass(frozen=True)
class TownBuild:
    """조립 결과. `tracker`는 시나리오 지표를 모으려는 쪽만 쓴다."""

    scenario: ScenarioConfig
    simulation: TownSimulation
    residents: list[Resident]
    configs: list[ResidentConfig]

    def new_tracker(self) -> ScenarioTracker:
        return ScenarioTracker(focus_event(self.configs, self.scenario))


def assemble_town(
    scenario: ScenarioConfig,
    *,
    configs: Sequence[ResidentConfig],
    space: Space,
    mind_factory: MindFactory,
    seed: int,
) -> TownBuild:
    """마음 선택·시나리오가 이미 적용된 설정으로 시뮬레이션을 만든다."""
    residents = [Resident(config, space, mind_factory) for config in configs]
    simulation = TownSimulation(
        space=space,
        residents=residents,
        clock=SimClock(scenario.start_time),
        rng=random.Random(seed),
    )
    return TownBuild(
        scenario=scenario,
        simulation=simulation,
        residents=residents,
        configs=list(configs),
    )


def build_llm_client() -> ProviderClient:
    """설정(`settings`)대로 만든 LLM 클라이언트. 감싸서 `build_town`에 넘길 수 있다."""
    return build_provider_client(
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        generation_model=LLM_MODEL,
        embedding_model=EMBEDDING_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY or None,
        embedding_base_url=EMBEDDING_BASE_URL,
        embedding_api_key=EMBEDDING_API_KEY or None,
        reasoning_effort=LLM_REASONING_EFFORT,
    )


def _llm_factory(
    configs: Sequence[ResidentConfig],
    space: Space,
    llm_client: ProviderClient | None,
) -> LLMMindFactory | None:
    if all(config.mind != "llm" for config in configs):
        return None
    return LLMMindFactory(
        client=llm_client if llm_client is not None else build_llm_client(),
        embedding_model=EMBEDDING_MODEL,
        known_places=space.location_paths(),
    )


def build_town(
    scenario: ScenarioConfig,
    *,
    agent_ids: Sequence[str] | None = None,
    agent_count: int | None = None,
    seed: int = 0,
    llm_client: ProviderClient | None = None,
) -> TownBuild:
    """둘 다 비우면 전원 규칙 마음(LLM 호출 0)으로 마을을 만든다.

    `llm_client`를 주면 설정으로 만든 클라이언트 대신 쓴다(실측 기록, 테스트용 가짜).
    """
    if agent_ids is None and agent_count is None:
        agent_count = 0
    configs = apply_mind_selection(
        load_resident_configs(), agent_ids=agent_ids, agent_count=agent_count
    )
    configs = apply_scenario(configs, scenario)
    space = load_town_space()
    factory = ResidentMindFactory(
        start_time=scenario.start_time,
        seed=seed,
        llm_factory=_llm_factory(configs, space, llm_client),
    )
    return assemble_town(
        scenario, configs=configs, space=space, mind_factory=factory, seed=seed
    )
