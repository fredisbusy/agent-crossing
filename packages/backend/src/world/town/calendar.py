"""마을 달력: 날짜별 기념일 (SPEC §14). 모든 마음에 같은 형식으로 알린다."""

import datetime
from collections.abc import Mapping

from minds.social import josa
from world.contracts import Holiday, LocationPath, Observation

DEFAULT_HOLIDAYS: Mapping[tuple[int, int], Holiday] = {
    (1, 1): Holiday(
        name="새해",
        customs=("이웃과 새해 인사를 나눈다.",),
        greetings=("새해 복 많이 받으세요!",),
    ),
    (2, 14): Holiday(
        name="밸런타인데이",
        customs=("좋아하는 사람이나 고마운 이웃에게 초콜릿을 건네며 마음을 전한다.",),
        greetings=("해피 밸런타인데이!", "오늘 밸런타인데이네요!"),
        gift_item="초콜릿",
    ),
    (10, 31): Holiday(
        name="핼러윈",
        customs=("분장을 하고 이웃과 사탕을 나눈다.",),
        greetings=("해피 핼러윈!",),
        gift_item="사탕",
    ),
    (12, 25): Holiday(
        name="크리스마스",
        customs=("가까운 사람과 작은 선물을 주고받는다.",),
        greetings=("메리 크리스마스!",),
        gift_item="작은 선물",
    ),
}
"""(월, 일) → 기념일."""


class TownCalendar:
    def __init__(
        self, holidays: Mapping[tuple[int, int], Holiday] | None = None
    ) -> None:
        self._holidays = dict(DEFAULT_HOLIDAYS if holidays is None else holidays)

    def holidays_on(self, day: datetime.date) -> tuple[Holiday, ...]:
        found = self._holidays.get((day.month, day.day))
        return (found,) if found is not None else ()


def holiday_observation(
    holiday: Holiday, at: datetime.datetime, where: LocationPath
) -> Observation:
    customs = " ".join(holiday.customs)
    text = f"오늘은 {josa(holiday.name, '이다', '다')}. {customs}".strip()
    return Observation(kind="event", text=text, observed_at=at, location_path=where)

