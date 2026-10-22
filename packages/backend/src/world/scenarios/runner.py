"""시나리오 한 번 실행: 씨앗을 심은 주민으로 마을을 돌리고 지표를 낸다 (SPEC §16)."""

import random
from collections.abc import Callable, Sequence

from world.contracts import Space
from world.residents import MindFactory, Resident, ResidentConfig
from world.town import SimClock, TownSimulation

from .contracts import ScenarioConfig, ScenarioReport
from .loader import focus_event
from .report import ScenarioTracker


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
    residents = [Resident(config, space, mind_factory) for config in configs]
    sim = TownSimulation(
        space=space,
        residents=residents,
        clock=SimClock(scenario.start_time),
        rng=random.Random(seed),
    )
    tracker = ScenarioTracker(focus_event(configs, scenario))
    for minute in range(scenario.minutes):
        await sim.tick()
        tracker.sample(residents, sim.clock.now)
        if on_hour is not None and (minute + 1) % 60 == 0:
            on_hour(sim)
    return tracker.report(
        scenario=scenario.name, residents=residents, mind_calls=sim.mind_calls
    )
