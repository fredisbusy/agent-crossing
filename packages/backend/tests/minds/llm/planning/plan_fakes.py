"""시간·분 단위 분해 테스트용 가짜 planner. 하루 계획 9~12시 공원 산책을 한 시간씩, 분 단위로 쪼갠다."""

import datetime

from agents.planning.models import DayPlanItem, HourlyPlanItem, MinutePlanItem
from llm_fakes import FixedPlanner

STEP = datetime.timedelta(minutes=15)


class LayeredPlanner(FixedPlanner):
    """시간 단위는 한 시간씩, 분 단위는 current_time부터 horizon 동안 15분씩 낸다."""

    def __init__(
        self,
        *,
        horizon_minutes: int = 60,
        minute_location: str = "Johnson Park Garden",
        fail_minutes: bool = False,
        empty_hourly: bool = False,
    ) -> None:
        super().__init__()
        self._horizon = datetime.timedelta(minutes=horizon_minutes)
        self._minute_location = minute_location
        self._fail_minutes = fail_minutes
        self._empty_hourly = empty_hourly

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        self.hourly_calls.append((current_time, day_plan_item))
        if self._empty_hourly:
            return []
        items: list[HourlyPlanItem] = []
        start = day_plan_item.start_time
        while start < day_plan_item.end_time:
            end = min(start + datetime.timedelta(hours=1), day_plan_item.end_time)
            items.append(
                HourlyPlanItem(
                    start_time=start,
                    end_time=end,
                    location=day_plan_item.location,
                    action_content=f"{start:%H시} 산책",
                )
            )
            start = end
        return items

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        self.minute_calls.append((current_time, hourly_plan_item))
        if self._fail_minutes:
            raise RuntimeError("llm down")
        stop = min(current_time + self._horizon, hourly_plan_item.end_time)
        items: list[MinutePlanItem] = []
        start = current_time.replace(second=0, microsecond=0)
        while start < stop:
            end = min(start + STEP, stop)
            if (end - start) < datetime.timedelta(minutes=5):
                break
            items.append(
                MinutePlanItem(
                    start_time=start,
                    end_time=end,
                    location=self._minute_location,
                    action_content=f"{start:%H:%M} 걷는다",
                )
            )
            start = end
        return items
