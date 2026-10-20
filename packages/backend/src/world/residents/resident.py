"""주민 = 설정 + 몸 + 마음 + 대기 관찰 큐 (SPEC §12)."""

from typing import Protocol

from world.contracts import Mind, Observation, ResidentPublicView, Space

from .body import Body
from .config import ResidentConfig


class MindFactory(Protocol):
    """설정에서 마음을 만든다. 구현은 `minds` 쪽이 주입한다."""

    def build(self, config: ResidentConfig) -> Mind: ...


class Resident:
    """마을의 한 주민. 마음 종류는 `config.mind`에만 있고 공개 뷰에는 없다."""

    def __init__(
        self, config: ResidentConfig, space: Space, mind_factory: MindFactory
    ) -> None:
        self.config = config
        self.mind: Mind = mind_factory.build(config)
        self.body = Body(
            resident_id=config.resident_id,
            display_name=config.display_name,
            space=space,
            start_location=config.start_location,
        )
        self.pending: list[Observation] = []
        """마음이 아직 받지 않은 관찰."""

    @property
    def resident_id(self) -> str:
        return self.config.resident_id

    def public_view(self) -> ResidentPublicView:
        state = self.body.state
        return ResidentPublicView(
            resident_id=self.config.resident_id,
            display_name=self.config.display_name,
            location_path=state.location_path,
            action_description=state.action.description if state.action else None,
        )

    def drain_observations(self) -> tuple[Observation, ...]:
        drained = tuple(self.pending)
        self.pending.clear()
        return drained
