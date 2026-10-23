import datetime
from dataclasses import dataclass
from typing import Callable, TypeVar, cast

from llm.clients.types import JsonObject

from .json_utils import attempt_json_repair_once, parse_json_object
from .models import DayPlanItem, HourlyPlanItem, MinutePlanItem


@dataclass(frozen=True)
class DayPlanParseResult:
    items: list[DayPlanItem]


class DayPlanParseError(ValueError):
    reason: str

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class HourPlanParseResult:
    items: list[HourlyPlanItem]


class HourPlanParseError(ValueError):
    reason: str

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class MinutePlanParseResult:
    items: list[MinutePlanItem]


class MinutePlanParseError(ValueError):
    reason: str

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def try_parse_day_plan(
    response_text: str,
    *,
    min_items: int = 5,
    max_items: int = 8,
    reference_date: datetime.date | None = None,
) -> DayPlanParseResult:
    payload = parse_json_object(response_text)
    if payload is None:
        payload = attempt_json_repair_once(response_text)
    if payload is None:
        raise DayPlanParseError("json_parse_error_or_non_object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise DayPlanParseError("missing_or_invalid_items")

    normalized = _normalize_plan_items(
        raw_items=cast(list[object], raw_items),
        item_factory=DayPlanItem,
        min_duration=1,
        require_exact_minute=True,
        reference_date=reference_date,
    )
    if len(normalized) > max_items:
        normalized = normalized[:max_items]
    if len(normalized) < min_items:
        raise DayPlanParseError("insufficient_day_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    return DayPlanParseResult(items=normalized)


def try_parse_hour_plan(
    response_text: str,
    *,
    min_items: int = 1,
    max_items: int = 24,
    reference_date: datetime.date | None = None,
) -> HourPlanParseResult:
    payload = parse_json_object(response_text)
    if payload is None:
        payload = attempt_json_repair_once(response_text)
    if payload is None:
        raise HourPlanParseError("json_parse_error_or_non_object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise HourPlanParseError("missing_or_invalid_items")

    normalized = _normalize_plan_items(
        raw_items=cast(list[object], raw_items),
        item_factory=HourlyPlanItem,
        min_duration=1,
        require_exact_minute=True,
        reference_date=reference_date,
    )
    if len(normalized) > max_items:
        normalized = normalized[:max_items]
    if len(normalized) < min_items:
        raise HourPlanParseError("insufficient_hour_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    return HourPlanParseResult(items=normalized)


def try_parse_minute_plan(
    response_text: str,
    *,
    min_items: int = 1,
    max_items: int = 500,
    reference_date: datetime.date | None = None,
) -> MinutePlanParseResult:
    payload = parse_json_object(response_text)
    if payload is None:
        payload = attempt_json_repair_once(response_text)
    if payload is None:
        raise MinutePlanParseError("json_parse_error_or_non_object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise MinutePlanParseError("missing_or_invalid_items")

    normalized = _normalize_plan_items(
        raw_items=cast(list[object], raw_items),
        item_factory=MinutePlanItem,
        min_duration=5,
        max_duration=15,
        require_exact_minute=True,
        reference_date=reference_date,
    )
    if len(normalized) > max_items:
        normalized = normalized[:max_items]
    if len(normalized) < min_items:
        raise MinutePlanParseError("insufficient_minute_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    return MinutePlanParseResult(items=normalized)


def _parse_iso_datetime(raw_value: object) -> datetime.datetime | None:
    if not isinstance(raw_value, str):
        return None

    value = raw_value.strip()
    if not value:
        return None

    candidate = value.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return None


TPlan = TypeVar("TPlan", DayPlanItem, HourlyPlanItem, MinutePlanItem)


def _normalize_plan_items(
    *,
    raw_items: list[object],
    item_factory: Callable[[datetime.datetime, datetime.datetime, str, str], TPlan],
    min_duration: int,
    max_duration: int | None = None,
    require_exact_minute: bool = False,
    reference_date: datetime.date | None = None,
) -> list[TPlan]:
    normalized: list[TPlan] = []
    seen: set[tuple[str, str, str, str]] = set()

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        payload = cast(JsonObject, raw_item)

        start_time = _parse_iso_datetime(payload.get("start_time"))
        end_time = _parse_iso_datetime(payload.get("end_time"))
        if start_time is None or end_time is None:
            continue
        start_time = _coerce_reference_year(start_time, reference_date)
        end_time = _coerce_reference_year(end_time, reference_date)
        if require_exact_minute and (
            not _is_exact_minute(start_time) or not _is_exact_minute(end_time)
        ):
            continue
        duration_minutes = _duration_minutes_between(start_time, end_time)
        if duration_minutes < min_duration:
            continue
        if max_duration is not None and duration_minutes > max_duration:
            continue

        if end_time <= start_time:
            continue

        location = payload.get("location")
        if not isinstance(location, str) or not location.strip():
            continue

        action_content = payload.get("action_content")
        if not isinstance(action_content, str) or not action_content.strip():
            continue

        normalized_location = location.strip()
        normalized_action_content = action_content.strip()
        dedupe_key = (
            start_time.isoformat(),
            end_time.isoformat(),
            normalized_location.casefold(),
            normalized_action_content.casefold(),
        )
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        normalized.append(
            item_factory(
                start_time,
                end_time,
                normalized_location,
                normalized_action_content,
            )
        )

    return normalized


def _duration_minutes_between(
    start_time: datetime.datetime, end_time: datetime.datetime
) -> int:
    return int((end_time - start_time).total_seconds() // 60)


def _coerce_reference_year(
    value: datetime.datetime,
    reference_date: datetime.date | None,
) -> datetime.datetime:
    if reference_date is None:
        return value
    if value.year == reference_date.year:
        return value
    if value.month != reference_date.month or value.day != reference_date.day:
        return value
    try:
        return value.replace(year=reference_date.year)
    except ValueError:
        return value


def _is_exact_minute(value: datetime.datetime) -> bool:
    return value.second == 0 and value.microsecond == 0
