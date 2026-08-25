import json
import datetime
from dataclasses import dataclass, replace
from typing import Callable, TypeVar, cast

from agents.planning.react_gate_contracts import (
    PlanDisruptionDecision,
    PlanDisruptionTrace,
)
from agents.reaction.contracts import (
    ReactionDecision,
    ReactionDecisionTrace,
    ReactionIntent,
    ReactionUtterance,
)
from agents.reaction.encounter_contracts import (
    EncounterDecision,
    EncounterDecisionTrace,
)
from agents.planning.models import DayPlanItem, HourlyPlanItem, MinutePlanItem
from llm.clients.types import JsonObject
from llm.structured_outputs import (
    DAY_ACTION_MAX_CHARS,
    DAY_LOCATION_MAX_CHARS,
    HOURLY_ACTION_MAX_CHARS,
    MINUTE_ACTION_MAX_CHARS,
)


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


@dataclass(frozen=True)
class MinuteTaskDecompositionItem:
    action_content: str
    duration_minutes: int


@dataclass(frozen=True)
class MinuteTaskDecompositionParseResult:
    items: list[MinuteTaskDecompositionItem]


def try_parse_day_plan(
    response_text: str,
    *,
    min_items: int = 5,
    max_items: int = 8,
    min_duration: int = 1,
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
        min_duration=min_duration,
        require_exact_minute=True,
        reference_date=reference_date,
        action_content_max_chars=DAY_ACTION_MAX_CHARS,
        location_max_chars=DAY_LOCATION_MAX_CHARS,
    )
    if len(normalized) < min_items:
        raise DayPlanParseError("insufficient_day_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    normalized = _compact_day_plan_items(normalized, max_items=max_items)
    return DayPlanParseResult(items=normalized)


def _compact_day_plan_items(
    items: list[DayPlanItem], *, max_items: int
) -> list[DayPlanItem]:
    """Merge the shortest continuous draft strokes without inventing content."""
    compacted = list(items)
    while len(compacted) > max_items:
        candidates: list[tuple[int, int, int]] = []
        for index, (first, second) in enumerate(zip(compacted, compacted[1:])):
            if first.end_time != second.start_time:
                continue
            location_penalty = 0 if first.location == second.location else 1
            combined_duration = first.duration_minutes + second.duration_minutes
            candidates.append((location_penalty, combined_duration, index))
        if not candidates:
            raise DayPlanParseError("too_many_non_contiguous_day_plan_items")
        _, _, merge_index = min(candidates)
        first = compacted[merge_index]
        second = compacted[merge_index + 1]
        dominant = (
            first if first.duration_minutes >= second.duration_minutes else second
        )
        compacted[merge_index : merge_index + 2] = [
            DayPlanItem(
                start_time=first.start_time,
                end_time=second.end_time,
                location=dominant.location,
                action_content=dominant.action_content,
            )
        ]
    return compacted


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
        action_content_max_chars=HOURLY_ACTION_MAX_CHARS,
    )
    if len(normalized) > max_items:
        normalized = normalized[:max_items]
    if len(normalized) < min_items:
        raise HourPlanParseError("insufficient_hour_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    return HourPlanParseResult(items=normalized)


def try_parse_hour_plan_decomposition(
    response_text: str,
    *,
    authoritative_location: str,
    reference_date: datetime.date | None = None,
) -> HourPlanParseResult:
    """Parse hourly timing/actions while inheriting location from the day parent."""
    payload = parse_json_object(response_text)
    if payload is None:
        payload = attempt_json_repair_once(response_text)
    if payload is None:
        raise HourPlanParseError("json_parse_error_or_non_object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise HourPlanParseError("missing_or_invalid_items")

    authoritative_items: list[object] = []
    for raw_item in cast(list[object], raw_items):
        if not isinstance(raw_item, dict):
            authoritative_items.append(raw_item)
            continue
        item = dict(cast(JsonObject, raw_item))
        item["location"] = authoritative_location
        authoritative_items.append(item)

    normalized = _normalize_plan_items(
        raw_items=authoritative_items,
        item_factory=HourlyPlanItem,
        min_duration=1,
        max_duration=180,
        require_exact_minute=True,
        reference_date=reference_date,
    )
    if not normalized:
        raise HourPlanParseError("insufficient_hour_plan_items")
    if len(normalized) > 24:
        raise HourPlanParseError("too_many_hour_plan_items")
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
        action_content_max_chars=MINUTE_ACTION_MAX_CHARS,
    )
    if len(normalized) > max_items:
        normalized = normalized[:max_items]
    if len(normalized) < min_items:
        raise MinutePlanParseError("insufficient_minute_plan_items")

    normalized.sort(key=lambda item: item.start_time)
    return MinutePlanParseResult(items=normalized)


def try_parse_minute_task_decomposition(
    response_text: str,
    *,
    expected_duration_minutes: int,
) -> MinuteTaskDecompositionParseResult:
    """Parse and fit paper-style task decomposition to a fixed total duration."""
    payload = parse_json_object(response_text)
    if payload is None:
        payload = attempt_json_repair_once(response_text)
    if payload is None:
        raise MinutePlanParseError("json_parse_error_or_non_object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise MinutePlanParseError("missing_or_invalid_items")
    typed_raw_items = cast(list[object], raw_items)
    if len(typed_raw_items) > 36:
        raise MinutePlanParseError("too_many_task_decomposition_items")

    items: list[MinuteTaskDecompositionItem] = []
    for raw_item in typed_raw_items:
        if not isinstance(raw_item, dict):
            raise MinutePlanParseError("invalid_task_decomposition_item")
        item = cast(JsonObject, raw_item)
        duration_minutes = item.get("duration_minutes")
        if (
            not isinstance(duration_minutes, int)
            or isinstance(duration_minutes, bool)
            or duration_minutes < 5
            or duration_minutes > 15
            or duration_minutes % 5 != 0
        ):
            raise MinutePlanParseError("invalid_duration_minutes")
        action_content = item.get("action_content")
        if not isinstance(action_content, str) or not action_content.strip():
            raise MinutePlanParseError("missing_or_invalid_action_content")
        if len(action_content.strip()) > MINUTE_ACTION_MAX_CHARS:
            raise MinutePlanParseError("action_content_too_long")
        items.append(
            MinuteTaskDecompositionItem(
                action_content=action_content.strip(),
                duration_minutes=duration_minutes,
            )
        )

    actual_duration_minutes = sum(item.duration_minutes for item in items)
    if actual_duration_minutes < expected_duration_minutes:
        deficit = expected_duration_minutes - actual_duration_minutes
        last = items[-1]
        items[-1] = MinuteTaskDecompositionItem(
            action_content=last.action_content,
            duration_minutes=last.duration_minutes + deficit,
        )
    elif actual_duration_minutes > expected_duration_minutes:
        remaining = expected_duration_minutes
        fitted: list[MinuteTaskDecompositionItem] = []
        for item in items:
            if remaining <= 0:
                break
            fitted_duration = min(item.duration_minutes, remaining)
            if fitted_duration < 1:
                raise MinutePlanParseError("fixed_window_is_not_positive")
            fitted.append(
                MinuteTaskDecompositionItem(
                    action_content=item.action_content,
                    duration_minutes=fitted_duration,
                )
            )
            remaining -= fitted_duration
        items = fitted

    fitted_total_minutes = sum(item.duration_minutes for item in items)
    if not items or fitted_total_minutes != expected_duration_minutes:
        raise MinutePlanParseError("unable_to_fit_fixed_duration_window")
    return MinuteTaskDecompositionParseResult(items=items)


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


def parse_reaction_decision(response_text: str) -> ReactionDecision:
    default_trace = ReactionDecisionTrace(
        raw_response=response_text,
        parse_success=False,
        parse_error="json_parse_error_or_non_object",
        fallback_reason="parse_failure",
    )
    default_value = ReactionDecision(
        should_react=False,
        reaction="",
        reason="fallback",
        end_dialogue=False,
        thought="",
        critique="",
        trace=default_trace,
    )
    parsed_json = parse_json_object(response_text)
    repaired_once = False
    if parsed_json is None:
        repaired_payload = attempt_json_repair_once(response_text)
        if repaired_payload is not None:
            parsed_json = repaired_payload
            repaired_once = True
        else:
            return default_value

    raw_should_react = parsed_json.get("should_react")
    if not isinstance(raw_should_react, bool):
        return replace(
            default_value,
            trace=replace(default_trace, parse_error="missing_or_invalid_should_react"),
        )

    raw_utterance = parsed_json.get("utterance")
    if not isinstance(raw_utterance, str):
        raw_utterance = ""

    raw_reaction = parsed_json.get("reaction")
    if not isinstance(raw_reaction, str):
        raw_reaction = ""
    final_reaction = raw_utterance.strip() or raw_reaction.strip()

    raw_thought = parsed_json.get("thought")
    if not isinstance(raw_thought, str):
        raw_thought = ""

    raw_critique = parsed_json.get("critique")
    if not isinstance(raw_critique, str):
        raw_critique = ""

    raw_reason = parsed_json.get("reason")
    if not isinstance(raw_reason, str):
        raw_reason = raw_critique or raw_thought or ""

    raw_end_dialogue = parsed_json.get("end_dialogue")
    end_dialogue = raw_end_dialogue if isinstance(raw_end_dialogue, bool) else False

    return ReactionDecision(
        should_react=raw_should_react,
        reaction=final_reaction,
        reason=raw_reason.strip() or "n/a",
        end_dialogue=end_dialogue,
        thought=raw_thought.strip(),
        critique=raw_critique.strip(),
        trace=ReactionDecisionTrace(
            raw_response=response_text,
            parse_success=True,
            parse_error="repaired_once" if repaired_once else "",
        ),
    )


def parse_reaction_intent(response_text: str) -> ReactionIntent:
    default_trace = ReactionDecisionTrace(
        raw_response=response_text,
        parse_success=False,
        parse_error="json_parse_error_or_non_object",
        fallback_reason="parse_failure",
    )
    default_value = ReactionIntent(
        should_react=False,
        reason="fallback",
        end_dialogue=False,
        thought="",
        critique="",
        trace=default_trace,
    )
    parsed_json = parse_json_object(response_text)
    repaired_once = False
    if parsed_json is None:
        repaired_payload = attempt_json_repair_once(response_text)
        if repaired_payload is not None:
            parsed_json = repaired_payload
            repaired_once = True
        else:
            return default_value

    raw_should_react = parsed_json.get("should_react")
    if not isinstance(raw_should_react, bool):
        return replace(
            default_value,
            trace=replace(default_trace, parse_error="missing_or_invalid_should_react"),
        )

    raw_thought = parsed_json.get("thought")
    if not isinstance(raw_thought, str):
        raw_thought = ""

    raw_critique = parsed_json.get("critique")
    if not isinstance(raw_critique, str):
        raw_critique = ""

    raw_reason = parsed_json.get("reason")
    if not isinstance(raw_reason, str):
        raw_reason = raw_critique or raw_thought or ""

    raw_end_dialogue = parsed_json.get("end_dialogue")
    end_dialogue = raw_end_dialogue if isinstance(raw_end_dialogue, bool) else False

    return ReactionIntent(
        should_react=raw_should_react,
        reason=raw_reason.strip() or "n/a",
        end_dialogue=end_dialogue,
        thought=raw_thought.strip(),
        critique=raw_critique.strip(),
        trace=ReactionDecisionTrace(
            raw_response=response_text,
            parse_success=True,
            parse_error="repaired_once" if repaired_once else "",
        ),
    )


def parse_reaction_utterance(response_text: str) -> ReactionUtterance:
    default_trace = ReactionDecisionTrace(
        raw_response=response_text,
        parse_success=False,
        parse_error="json_parse_error_or_non_object",
        fallback_reason="parse_failure",
    )
    default_value = ReactionUtterance(
        utterance="",
        reason="fallback",
        end_dialogue=False,
        thought="",
        critique="",
        trace=default_trace,
    )
    parsed_json = parse_json_object(response_text)
    repaired_once = False
    if parsed_json is None:
        repaired_payload = attempt_json_repair_once(response_text)
        if repaired_payload is not None:
            parsed_json = repaired_payload
            repaired_once = True
        else:
            return default_value

    raw_utterance = parsed_json.get("utterance")
    if not isinstance(raw_utterance, str):
        raw_utterance = ""

    raw_reaction = parsed_json.get("reaction")
    if not isinstance(raw_reaction, str):
        raw_reaction = ""
    final_utterance = raw_utterance.strip() or raw_reaction.strip()

    raw_thought = parsed_json.get("thought")
    if not isinstance(raw_thought, str):
        raw_thought = ""

    raw_critique = parsed_json.get("critique")
    if not isinstance(raw_critique, str):
        raw_critique = ""

    raw_reason = parsed_json.get("reason")
    if not isinstance(raw_reason, str):
        raw_reason = raw_critique or raw_thought or ""

    raw_end_dialogue = parsed_json.get("end_dialogue")
    end_dialogue = raw_end_dialogue if isinstance(raw_end_dialogue, bool) else False

    return ReactionUtterance(
        utterance=final_utterance,
        reason=raw_reason.strip() or "n/a",
        end_dialogue=end_dialogue,
        thought=raw_thought.strip(),
        critique=raw_critique.strip(),
        trace=ReactionDecisionTrace(
            raw_response=response_text,
            parse_success=True,
            parse_error="repaired_once" if repaired_once else "",
        ),
    )


TPlan = TypeVar("TPlan", DayPlanItem, HourlyPlanItem, MinutePlanItem)


def _normalize_plan_items(
    *,
    raw_items: list[object],
    item_factory: Callable[[datetime.datetime, datetime.datetime, str, str], TPlan],
    min_duration: int,
    max_duration: int | None = None,
    require_exact_minute: bool = False,
    reference_date: datetime.date | None = None,
    action_content_max_chars: int | None = None,
    location_max_chars: int | None = None,
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
        if (
            location_max_chars is not None
            and len(location.strip()) > location_max_chars
        ):
            continue

        action_content = payload.get("action_content")
        if not isinstance(action_content, str) or not action_content.strip():
            continue
        if (
            action_content_max_chars is not None
            and len(action_content.strip()) > action_content_max_chars
        ):
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


def parse_plan_disruption(response_text: str) -> PlanDisruptionDecision:
    default_trace = PlanDisruptionTrace(
        raw_response=response_text,
        parse_success=False,
        parse_error="json_parse_error_or_non_object",
    )
    parsed_json = parse_json_object(response_text)
    repaired_once = False
    if parsed_json is None:
        repaired_payload = attempt_json_repair_once(response_text)
        if repaired_payload is not None:
            parsed_json = repaired_payload
            repaired_once = True
        else:
            return PlanDisruptionDecision(
                should_react=False,
                reason="파싱 실패로 기존 계획을 유지함",
                trace=default_trace,
            )

    raw_should_react = parsed_json.get("should_react")
    if not isinstance(raw_should_react, bool):
        return PlanDisruptionDecision(
            should_react=False,
            reason="파싱 실패로 기존 계획을 유지함",
            trace=replace(default_trace, parse_error="missing_or_invalid_should_react"),
        )

    raw_reason = parsed_json.get("reason")
    if not isinstance(raw_reason, str) or not raw_reason.strip():
        raw_reason = "판단 근거 없음"

    return PlanDisruptionDecision(
        should_react=raw_should_react,
        reason=raw_reason.strip(),
        trace=PlanDisruptionTrace(
            raw_response=response_text,
            parse_success=True,
            parse_error="repaired_once" if repaired_once else "",
        ),
    )


def parse_encounter_decision(response_text: str) -> EncounterDecision:
    default_trace = EncounterDecisionTrace(
        raw_response=response_text,
        parse_success=False,
        parse_error="json_parse_error_or_non_object",
    )
    parsed_json = parse_json_object(response_text)
    repaired_once = False
    if parsed_json is None:
        repaired_payload = attempt_json_repair_once(response_text)
        if repaired_payload is not None:
            parsed_json = repaired_payload
            repaired_once = True
        else:
            return EncounterDecision(
                should_converse=True,
                relationship_summary="",
                context_summary="",
                reason="파싱 실패로 기본값(대화)을 적용함",
                trace=default_trace,
            )

    raw_should_converse = parsed_json.get("should_converse")
    if not isinstance(raw_should_converse, bool):
        return EncounterDecision(
            should_converse=True,
            relationship_summary="",
            context_summary="",
            reason="파싱 실패로 기본값(대화)을 적용함",
            trace=replace(
                default_trace, parse_error="missing_or_invalid_should_converse"
            ),
        )

    def _text(key: str) -> str:
        value = parsed_json.get(key)
        return value.strip() if isinstance(value, str) else ""

    return EncounterDecision(
        should_converse=raw_should_converse,
        relationship_summary=_text("relationship_summary"),
        context_summary=_text("context_summary"),
        reason=_text("reason") or "판단 근거 없음",
        trace=EncounterDecisionTrace(
            raw_response=response_text,
            parse_success=True,
            parse_error="repaired_once" if repaired_once else "",
        ),
    )


def parse_json_object(text: str) -> JsonObject | None:
    try:
        parsed = cast(object, json.loads(text))
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return cast(JsonObject, parsed)


def attempt_json_repair_once(text: str) -> JsonObject | None:
    candidate = text.strip()
    if not candidate:
        return None

    first_open = candidate.find("{")
    if first_open > 0:
        candidate = candidate[first_open:]

    last_close = candidate.rfind("}")
    if last_close >= 0:
        candidate = candidate[: last_close + 1]

    open_count = candidate.count("{")
    close_count = candidate.count("}")
    if open_count > close_count:
        candidate = candidate + ("}" * (open_count - close_count))

    return parse_json_object(candidate)
