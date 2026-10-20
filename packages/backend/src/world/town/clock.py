"""주입 가능한 시뮬레이션 시계 (SPEC §14)."""

import datetime


class SimClock:
    """게임 시간 시계. 실제 시계를 읽지 않고 `advance`로만 흐른다."""

    def __init__(self, start: datetime.datetime) -> None:
        self._now = start

    @property
    def now(self) -> datetime.datetime:
        return self._now

    def advance(self, minutes: int = 1) -> datetime.datetime:
        self._now += datetime.timedelta(minutes=minutes)
        return self._now
