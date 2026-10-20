"""몸: 경로 따라 걷고 행동을 이어 가는 LLM 없는 실행기 (SPEC §12)."""

import datetime

from world.contracts import (
    ActionIntent,
    BodyState,
    LocationPath,
    Observation,
    ResidentId,
    Space,
    TilePosition,
)


class Body:
    """한 주민의 몸. 틱마다 경로를 1타일 전진하고 행동 만료를 판단한다."""

    def __init__(
        self,
        *,
        resident_id: ResidentId,
        display_name: str,
        space: Space,
        start_location: LocationPath,
    ) -> None:
        tile = space.tile_of(start_location)
        if tile is None:
            raise ValueError(f"시작 위치를 찾을 수 없다: {start_location}")
        self._resident_id = resident_id
        self._display_name = display_name
        self._space = space
        self._tile = tile
        self._location_path = space.location_at(tile)
        self._action: ActionIntent | None = None
        self._path: tuple[TilePosition, ...] = ()
        self.conversation_id: str | None = None

    @property
    def state(self) -> BodyState:
        return BodyState(
            resident_id=self._resident_id,
            display_name=self._display_name,
            tile=self._tile,
            location_path=self._location_path,
            action=self._action,
            path=self._path,
            conversation_id=self.conversation_id,
        )

    @property
    def is_moving(self) -> bool:
        return bool(self._path)

    def is_expired(self, now: datetime.datetime) -> bool:
        """진행 중인 행동이 없거나 `until <= now`면 True."""
        return self._action is None or self._action.until <= now

    def set_intent(
        self, intent: ActionIntent, now: datetime.datetime
    ) -> Observation | None:
        """행동을 받는다. 갈 수 없으면 제자리 idle로 바꾸고 관찰을 돌려 준다."""
        self._path = ()
        if intent.location_path == self._location_path:
            self._action = intent
            return None
        goal = self._space.tile_of(intent.location_path)
        path = self._space.find_path(self._tile, goal) if goal is not None else None
        if path is None:
            self._action = ActionIntent(
                kind="idle",
                description="제자리에 머문다",
                location_path=self._location_path,
                until=intent.until,
            )
            return Observation(
                kind="event",
                text=f"{intent.location_path}로 갈 수 없었다",
                observed_at=now,
                location_path=self._location_path,
                subject_id=self._resident_id,
            )
        self._action = intent
        self._path = path
        return None

    def step(self) -> None:
        """대화 중이 아니면 경로를 1타일 전진하고 위치 경로를 갱신한다."""
        if self.conversation_id is not None or not self._path:
            return
        self._tile, self._path = self._path[0], self._path[1:]
        self._location_path = self._space.location_at(self._tile)
