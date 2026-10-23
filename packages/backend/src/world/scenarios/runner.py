"""시나리오 한 번 실행: 씨앗을 심은 주민으로 마을을 돌리고 지표를 낸다 (SPEC §16)."""

from collections.abc import Callable, Sequence

from world.contracts import Space
from world.residents import MindFactory, ResidentConfig
from world.town import TownSimulation

from .build import TownBuild, assemble_town
from .contracts import ScenarioConfig, ScenarioReport


async def simulate(
    town: TownBuild,
    *,
    on_hour: Callable[[TownSimulation], None] | None = None,
) -> ScenarioReport:
    """조립된 마을을 시나리오 길이만큼 돌린다."""
    sim = town.simulation
    tracker = town.new_tracker()
    for minute in range(town.scenario.minutes):
        await sim.tick()
        tracker.sample(town.residents, sim.clock.now)
        if on_hour is not None and (minute + 1) % 60 == 0:
            on_hour(sim)
    return tracker.report(
        scenario=town.scenario.name,
        residents=town.residents,
        mind_calls=sim.mind_calls,
    )


async def run_scenario(
    scenario: ScenarioConfig,
    *,
    configs: Sequence[ResidentConfig],
    space: Space,
    mind_factory: MindFactory,
    seed: int = 0,
    on_hour: Callable[[TownSimulation], None] | None = None,
) -> ScenarioReport:
    """`configs`에는 시나리오(`apply_scenario`)와 마음 선택이 이미 적용돼 있어야 한다."""
    town = assemble_town(
        scenario, configs=configs, space=space, mind_factory=mind_factory, seed=seed
    )
    return await simulate(town, on_hour=on_hour)
