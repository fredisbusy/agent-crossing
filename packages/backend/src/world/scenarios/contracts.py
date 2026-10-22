"""시나리오 씨앗과 결과 리포트 스키마 (SPEC §16)."""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from world.contracts import ResidentId, SocialEvent
from world.residents import SeedFact


class ResidentPatch(BaseModel):
    """시나리오가 주민 설정 위에 더하는 시작 상태. 두 마음에 똑같이 적용된다."""

    model_config = ConfigDict(frozen=True)

    hosting: list[SocialEvent] = Field(default_factory=list)
    seed_facts: list[SeedFact] = Field(default_factory=list)
    friendships: dict[ResidentId, int] = Field(default_factory=dict)
    seed_memories: list[str] = Field(default_factory=list)


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    title: str
    start_time: datetime.datetime
    minutes: int = Field(gt=0)
    """시뮬레이션할 게임 시간(분)."""
    focus_event: str
    """리포트가 확산·참석을 세는 행사 이름."""
    residents: dict[ResidentId, ResidentPatch] = Field(default_factory=dict)


class ScenarioReport(BaseModel):
    """SPEC §16 비교 지표. 주최자는 세지 않는다."""

    model_config = ConfigDict(frozen=True)

    scenario: str
    event: str
    resident_count: int
    agent_ids: tuple[ResidentId, ...]
    knew_event: tuple[ResidentId, ...]
    """행사를 알게 된 주민."""
    committed: tuple[ResidentId, ...]
    """가기로 한 주민."""
    attended: tuple[ResidentId, ...]
    """가기로 하고 행사 시간에 행사 건물에 온 주민."""
    present: tuple[ResidentId, ...]
    """약속과 무관하게 행사 시간에 행사 건물에 있었던 주민(지나가던 사람 포함)."""
    mind_calls: dict[str, int]
    """마음 종류별 호출 수."""

    @property
    def diffusion_rate(self) -> float:
        others = self.resident_count - 1
        return len(self.knew_event) / others if others > 0 else 0.0
