"""설정에서 마음을 만드는 팩토리 (SPEC §12)."""

import datetime
import random

from minds.schedule import build_schedule_mind, load_archetype
from minds.social import HasSocialState, SocialSeed
from world.contracts import Mind

from .config import ResidentConfig
from .resident import MindFactory


def social_seed(config: ResidentConfig) -> SocialSeed:
    """설정의 여는 행사·사실·우호도를 두 마음 공통 시작 상태로 바꾼다."""
    return SocialSeed(
        hosting=tuple(config.hosting),
        facts=tuple((f.topic, f.fact) for f in config.seed_facts),
        friendships=dict(config.friendships),
    )


class ResidentMindFactory:
    """`mind` 값에 맞는 마음을 만들고, 마음 종류와 무관하게 같은 시작 상태를 심는다.

    규칙 마음은 `seed`와 주민 id로 고정된 난수를 받으므로 같은 seed면 같은 마을이 된다.
    LLM 주민은 `llm_factory`가 있으면 그쪽에 맡기고, 없으면 ValueError를 낸다.
    """

    def __init__(
        self,
        *,
        start_time: datetime.datetime,
        seed: int = 0,
        llm_factory: MindFactory | None = None,
    ) -> None:
        self._start_time = start_time
        self._seed = seed
        self._llm_factory = llm_factory

    def build(self, config: ResidentConfig) -> Mind:
        mind = self._build_mind(config)
        if isinstance(mind, HasSocialState):
            mind.social.apply_seed(social_seed(config), self._start_time)
        return mind

    def _build_mind(self, config: ResidentConfig) -> Mind:
        if config.mind == "llm":
            if self._llm_factory is None:
                raise ValueError(
                    f"{config.resident_id}: LLM 마음 팩토리가 주입되지 않았다"
                )
            return self._llm_factory.build(config)
        schedule = load_archetype(config.archetype, placeholders=config.placeholders)
        return build_schedule_mind(
            resident_id=config.resident_id,
            display_name=config.display_name,
            config=schedule,
            rng=random.Random(f"{self._seed}:{config.resident_id}"),
        )
