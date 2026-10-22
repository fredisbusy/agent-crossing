"""시나리오 JSON을 읽고 주민 설정에 시작 상태를 더한다."""

import json
from collections.abc import Sequence
from pathlib import Path

from world.contracts import SocialEvent
from world.residents import DEFAULT_RESIDENTS_DIR, ResidentConfig

from .contracts import ScenarioConfig

DEFAULT_SCENARIO_DIR = DEFAULT_RESIDENTS_DIR / "scenarios"


def load_scenario(name: str, directory: Path | None = None) -> ScenarioConfig:
    path = (directory or DEFAULT_SCENARIO_DIR) / f"{name}.json"
    return ScenarioConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


def apply_scenario(
    configs: Sequence[ResidentConfig], scenario: ScenarioConfig
) -> list[ResidentConfig]:
    known = {config.resident_id for config in configs}
    unknown = sorted(set(scenario.residents) - known)
    if unknown:
        raise ValueError(f"시나리오에 알 수 없는 주민 id: {', '.join(unknown)}")
    patched: list[ResidentConfig] = []
    for config in configs:
        patch = scenario.residents.get(config.resident_id)
        if patch is None:
            patched.append(config)
            continue
        patched.append(
            config.model_copy(
                update={
                    "hosting": [*config.hosting, *patch.hosting],
                    "seed_facts": [*config.seed_facts, *patch.seed_facts],
                    "friendships": {**config.friendships, **patch.friendships},
                    "seed_memories": [*config.seed_memories, *patch.seed_memories],
                }
            )
        )
    return patched


def focus_event(
    configs: Sequence[ResidentConfig], scenario: ScenarioConfig
) -> SocialEvent:
    """리포트 대상 행사(주최자 id를 채워서)."""
    for config in configs:
        for event in config.hosting:
            if event.name == scenario.focus_event:
                return event.model_copy(update={"host_id": config.resident_id})
    raise ValueError(f"주최자가 없는 행사: {scenario.focus_event}")
