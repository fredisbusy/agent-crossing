from __future__ import annotations

import datetime
import threading
import uuid
from collections.abc import Iterable, Mapping

from .models import (
    RelationshipEvent,
    RelationshipEventType,
    RelationshipMetrics,
    RelationshipState,
)
from .rules import DAILY_GROSS_CAPS, EVENT_DELTAS, METRIC_RANGES

MAX_RELATIONSHIP_EVENTS_PER_SESSION = 10_000


class RelationshipService:
    """Session-scoped, directional relationship state and auditable event ledger."""

    def __init__(
        self,
        agent_ids: Iterable[str],
        baselines: Mapping[tuple[str, str], RelationshipMetrics] | None = None,
        event_namespace: uuid.UUID | None = None,
    ) -> None:
        ids = tuple(dict.fromkeys(agent_ids))
        self._agent_ids = frozenset(ids)
        self._states = {
            (subject, target): RelationshipState(
                subject_agent_id=subject,
                target_agent_id=target,
                metrics=(baselines or {}).get((subject, target), RelationshipMetrics()),
            )
            for subject in ids
            for target in ids
            if subject != target
        }
        unknown_baselines = set(baselines or {}) - set(self._states)
        if unknown_baselines:
            raise ValueError(
                f"relationship baselines reference unknown pairs: {unknown_baselines}"
            )
        self._events: list[RelationshipEvent] = []
        self._event_keys: set[tuple[str, str, str, RelationshipEventType]] = set()
        self._event_namespace = event_namespace or uuid.uuid4()
        self._event_ids_verified = True
        self._lock = threading.RLock()

    def state_for(
        self, subject_agent_id: str, target_agent_id: str
    ) -> RelationshipState:
        with self._lock:
            return self._states[self._validate_pair(subject_agent_id, target_agent_id)]

    def states(self) -> tuple[RelationshipState, ...]:
        with self._lock:
            return tuple(self._states.values())

    def events(self) -> tuple[RelationshipEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @property
    def event_namespace(self) -> uuid.UUID:
        return self._event_namespace

    @property
    def event_ids_verified(self) -> bool:
        return self._event_ids_verified

    def recent_events(
        self, subject_agent_id: str, target_agent_id: str, *, limit: int = 5
    ) -> tuple[RelationshipEvent, ...]:
        self._validate_pair(subject_agent_id, target_agent_id)
        with self._lock:
            matches = [
                event
                for event in reversed(self._events)
                if event.subject_agent_id == subject_agent_id
                and event.target_agent_id == target_agent_id
            ]
            return tuple(matches[:limit])

    def pair_snapshot(
        self, subject_agent_id: str, target_agent_id: str, *, event_limit: int = 5
    ) -> tuple[RelationshipState, tuple[RelationshipEvent, ...]]:
        """Read one directional state and its recent ledger entries atomically."""
        pair = self._validate_pair(subject_agent_id, target_agent_id)
        with self._lock:
            events = tuple(
                event
                for event in reversed(self._events)
                if (event.subject_agent_id, event.target_agent_id) == pair
            )[:event_limit]
            return self._states[pair], events

    def record_event(
        self,
        *,
        subject_agent_id: str,
        target_agent_id: str,
        event_type: RelationshipEventType,
        source_event_id: str,
        occurred_at: datetime.datetime,
        source_kind: str = "runtime",
    ) -> RelationshipEvent | None:
        pair = self._validate_pair(subject_agent_id, target_agent_id)
        key = (subject_agent_id, target_agent_id, source_event_id, event_type)
        with self._lock:
            if key in self._event_keys:
                return None
            if len(self._events) >= MAX_RELATIONSHIP_EVENTS_PER_SESSION:
                raise RuntimeError(
                    "relationship event ledger reached its session limit"
                )
            before_state = self._states[pair]
            requested = EVENT_DELTAS[event_type]
            applied = self._bounded_delta(
                pair=pair,
                requested=requested,
                before=before_state.metrics,
                occurred_at=occurred_at,
            )
            after = RelationshipMetrics(
                familiarity=before_state.metrics.familiarity + applied.familiarity,
                trust=before_state.metrics.trust + applied.trust,
                affinity=before_state.metrics.affinity + applied.affinity,
                tension=before_state.metrics.tension + applied.tension,
                romantic_interest=(
                    before_state.metrics.romantic_interest + applied.romantic_interest
                ),
            )
            event_id = str(
                uuid.uuid5(
                    self._event_namespace,
                    "|".join((*pair, source_event_id, event_type.value)),
                )
            )
            event = RelationshipEvent(
                id=event_id,
                source_event_id=source_event_id,
                subject_agent_id=subject_agent_id,
                target_agent_id=target_agent_id,
                event_type=event_type,
                occurred_at=occurred_at,
                requested_delta=requested,
                applied_delta=applied,
                before=before_state.metrics,
                after=after,
                source_kind=source_kind,
            )
            self._states[pair] = RelationshipState(
                subject_agent_id=subject_agent_id,
                target_agent_id=target_agent_id,
                metrics=after,
                last_interaction_at=occurred_at,
                updated_at=occurred_at,
                revision=before_state.revision + 1,
            )
            self._events.append(event)
            self._event_keys.add(key)
            return event

    def restore(
        self,
        *,
        states: Iterable[RelationshipState],
        events: Iterable[RelationshipEvent],
        event_namespace: uuid.UUID | None = None,
        verify_event_ids: bool = True,
    ) -> None:
        restored_states = {
            (state.subject_agent_id, state.target_agent_id): state for state in states
        }
        restored_events = list(events)
        with self._lock:
            for pair in restored_states:
                self._validate_pair(*pair)
            expected_pairs = set(self._states)
            if set(restored_states) != expected_pairs:
                raise ValueError(
                    "relationship snapshot must contain every directional pair"
                )
            keys = {
                (
                    event.subject_agent_id,
                    event.target_agent_id,
                    event.source_event_id,
                    event.event_type,
                )
                for event in restored_events
            }
            if len(keys) != len(restored_events):
                raise ValueError(
                    "relationship event ledger contains duplicate source events"
                )
            if len({event.id for event in restored_events}) != len(restored_events):
                raise ValueError(
                    "relationship event ledger contains duplicate event ids"
                )
            if len(restored_events) > MAX_RELATIONSHIP_EVENTS_PER_SESSION:
                raise ValueError("relationship event ledger exceeds session limit")
            namespace = event_namespace or self._event_namespace
            first_event_before: dict[tuple[str, str], RelationshipMetrics] = {}
            for event in restored_events:
                pair = (event.subject_agent_id, event.target_agent_id)
                first_event_before.setdefault(pair, event.before)
            replay_metrics = {
                pair: first_event_before.get(pair, restored_states[pair].metrics)
                for pair in expected_pairs
            }
            replay_revisions = dict.fromkeys(expected_pairs, 0)
            replay_timestamps: dict[tuple[str, str], datetime.datetime | None] = (
                dict.fromkeys(expected_pairs)
            )
            replayed_events: list[RelationshipEvent] = []
            for event in restored_events:
                pair = self._validate_pair(
                    event.subject_agent_id, event.target_agent_id
                )
                if event.before != replay_metrics[pair]:
                    raise ValueError("relationship event chain is discontinuous")
                requested = EVENT_DELTAS[event.event_type]
                if event.requested_delta != requested:
                    raise ValueError(
                        "relationship event requested delta is not canonical"
                    )
                applied = self._bounded_delta(
                    pair=pair,
                    requested=requested,
                    before=event.before,
                    occurred_at=event.occurred_at,
                    events=replayed_events,
                )
                if event.applied_delta != applied:
                    raise ValueError(
                        "relationship event applied delta is not canonical"
                    )
                expected_after = RelationshipMetrics(
                    **{
                        metric: getattr(event.before, metric) + getattr(applied, metric)
                        for metric in METRIC_RANGES
                    }
                )
                if event.after != expected_after:
                    raise ValueError(
                        "relationship event after-state does not match delta"
                    )
                expected_id = str(
                    uuid.uuid5(
                        namespace,
                        "|".join(
                            (*pair, event.source_event_id, event.event_type.value)
                        ),
                    )
                )
                if verify_event_ids and event.id != expected_id:
                    raise ValueError(
                        "relationship event id does not match its namespace"
                    )
                replay_metrics[pair] = event.after
                replay_revisions[pair] += 1
                replay_timestamps[pair] = event.occurred_at
                replayed_events.append(event)
            expected_states = {
                pair: RelationshipState(
                    subject_agent_id=pair[0],
                    target_agent_id=pair[1],
                    metrics=replay_metrics[pair],
                    last_interaction_at=replay_timestamps[pair],
                    updated_at=replay_timestamps[pair],
                    revision=replay_revisions[pair],
                )
                for pair in expected_pairs
            }
            if restored_states != expected_states:
                raise ValueError("relationship state does not match its event ledger")
            self._states = restored_states
            self._events = restored_events
            self._event_keys = keys
            self._event_namespace = namespace
            self._event_ids_verified = verify_event_ids

    def _validate_pair(self, subject: str, target: str) -> tuple[str, str]:
        if subject == target:
            raise ValueError("relationship subject and target must differ")
        pair = (subject, target)
        if (
            subject not in self._agent_ids
            or target not in self._agent_ids
            or pair not in self._states
        ):
            raise KeyError(f"unknown relationship pair: {subject}->{target}")
        return pair

    def _bounded_delta(
        self,
        *,
        pair: tuple[str, str],
        requested: RelationshipMetrics,
        before: RelationshipMetrics,
        occurred_at: datetime.datetime,
        events: Iterable[RelationshipEvent] | None = None,
    ) -> RelationshipMetrics:
        ledger = self._events if events is None else events
        values: dict[str, int] = {}
        for metric in METRIC_RANGES:
            used = sum(
                abs(getattr(event.applied_delta, metric))
                for event in ledger
                if (event.subject_agent_id, event.target_agent_id) == pair
                and event.occurred_at.date() == occurred_at.date()
            )
            request = getattr(requested, metric)
            remaining = max(0, DAILY_GROSS_CAPS[metric] - used)
            capped = max(-remaining, min(remaining, request))
            low, high = METRIC_RANGES[metric]
            current = getattr(before, metric)
            values[metric] = max(low, min(high, current + capped)) - current
        return RelationshipMetrics(**values)
