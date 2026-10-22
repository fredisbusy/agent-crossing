"""주민 설정 모델과 로더 (SPEC §12)."""

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from world.contracts import LocationPath, MindKind, ResidentId, SocialEvent

DEFAULT_RESIDENTS_DIR = Path(__file__).resolve().parents[3] / "residents"
"""`packages/backend/residents/`."""


class SeedFact(BaseModel):
    """시작할 때 아는 사실."""

    model_config = ConfigDict(frozen=True)

    topic: str
    fact: str


class ResidentConfig(BaseModel):
    """주민 한 명의 설정. 몸·마음 구현과 무관한 데이터만 담는다."""

    model_config = ConfigDict(frozen=True)

    resident_id: ResidentId
    display_name: str
    age: int
    description: list[str]
    """정체성 문장. LLMMind 페르소나의 씨앗."""
    mind: MindKind = "schedule"
    agent_priority: int
    """작을수록 먼저 에이전트(llm)로 승격된다."""
    home_location: LocationPath
    start_location: LocationPath
    archetype: str
    """ScheduleMind 일정 원형 이름."""
    placeholders: dict[str, str] = Field(default_factory=dict)
    """원형의 `{home}`·`{bedroom}` 같은 자리표시자 치환값."""
    seed_memories: list[str] = Field(default_factory=list)
    """LLM 마음의 시작 기억 문장. 행사·사실은 아래 구조 필드로 두 마음이 함께 쓴다."""
    hosting: list[SocialEvent] = Field(default_factory=list)
    """이 주민이 여는 행사."""
    seed_facts: list[SeedFact] = Field(default_factory=list)
    friendships: dict[ResidentId, int] = Field(default_factory=dict)
    """시작 우호도(0~100)."""


def load_resident_configs(directory: Path | None = None) -> list[ResidentConfig]:
    """디렉터리의 `*.json`을 `agent_priority` 순으로 읽는다. 하위 폴더(`archetypes/`)는 제외."""
    base = directory if directory is not None else DEFAULT_RESIDENTS_DIR
    configs = [
        ResidentConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(base.glob("*.json"))
    ]
    return sorted(configs, key=lambda config: (config.agent_priority, config.resident_id))


def apply_mind_selection(
    configs: Sequence[ResidentConfig],
    *,
    agent_ids: Sequence[str] | None = None,
    agent_count: int | None = None,
) -> list[ResidentConfig]:
    """에이전트(llm)로 올릴 주민을 정한다. 둘 다 없으면 파일 값을 유지한다."""
    known = {config.resident_id for config in configs}
    if agent_ids is not None:
        unknown = [rid for rid in agent_ids if rid not in known]
        if unknown:
            raise ValueError(f"알 수 없는 주민 id: {', '.join(unknown)}")
        chosen = set(agent_ids)
    elif agent_count is not None:
        ranked = sorted(configs, key=lambda config: config.agent_priority)
        chosen = {config.resident_id for config in ranked[: max(agent_count, 0)]}
    else:
        return list(configs)
    return [
        config.model_copy(
            update={"mind": "llm" if config.resident_id in chosen else "schedule"}
        )
        for config in configs
    ]
