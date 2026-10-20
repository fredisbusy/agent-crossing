"""설정에서 마음을 만드는 팩토리 (SPEC §12)."""

import random

from minds.schedule import build_schedule_mind, load_archetype
from world.contracts import Mind

from .config import ResidentConfig
from .resident import MindFactory


class ScheduleMindFactory:
    """`mind="schedule"` 주민에게 원형 일정표로 ScheduleMind를 만든다.

    주민마다 `seed`와 주민 id로 고정된 난수를 주므로 같은 seed면 같은 마을이 된다.
    LLM 주민은 `llm_factory`가 있으면 그쪽에 맡기고, 없으면 ValueError를 낸다.
    """

    def __init__(self, *, seed: int = 0, llm_factory: MindFactory | None = None) -> None:
        self._seed = seed
        self._llm_factory = llm_factory

    def build(self, config: ResidentConfig) -> Mind:
        if config.mind == "llm":
            if self._llm_factory is None:
                raise ValueError(f"{config.resident_id}: LLM 마음 팩토리가 주입되지 않았다")
            return self._llm_factory.build(config)
        schedule = load_archetype(config.archetype, placeholders=config.placeholders)
        return build_schedule_mind(
            resident_id=config.resident_id,
            display_name=config.display_name,
            config=schedule,
            rng=random.Random(f"{self._seed}:{config.resident_id}"),
        )

