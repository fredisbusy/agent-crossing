import datetime
import threading
from collections import deque
from dataclasses import dataclass

from .engine import SimulationStepResult


@dataclass(frozen=True)
class DashboardEvent:
    """Diagnostics-owned record of one completed cognitive decision.

    `thought` is the curated, display-safe text (critique, falling back to
    reason) used for the in-world thought bubble overlay — it is not the
    model's raw reasoning. The unedited model output lives in
    `model_thought`; see `agents.decision_diagnostics.ActionDiagnostics`.
    """

    sequence: int
    turn: int
    occurred_at: datetime.datetime
    agent_id: str
    agent_name: str
    reply: str
    silent_reason: str
    parse_failure: bool
    thought: str
    model_thought: str
    self_critique: str
    decision_reason: str
    action_summary: str
    decision_process: dict[str, object]
    governance_trace: dict[str, object]


class DashboardEventBuffer:
    """Thread-safe bounded history for the operator dashboard."""

    def __init__(self, *, capacity: int = 500) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than zero")
        self._events: deque[DashboardEvent] = deque(maxlen=capacity)
        self._next_sequence: int = 1
        self._lock: threading.RLock = threading.RLock()

    def append(
        self,
        *,
        turn: int,
        agent_id: str,
        agent_name: str,
        result: SimulationStepResult,
    ) -> DashboardEvent:
        with self._lock:
            event = DashboardEvent(
                sequence=self._next_sequence,
                turn=turn,
                occurred_at=result.now,
                agent_id=agent_id,
                agent_name=agent_name,
                reply=result.reply,
                silent_reason=result.silent_reason,
                parse_failure=result.parse_failure,
                thought=result.observability.thought,
                model_thought=result.observability.model_thought,
                self_critique=result.observability.self_critique,
                decision_reason=result.observability.decision_reason,
                action_summary=result.observability.action_summary,
                decision_process=dict(result.observability.decision_process),
                governance_trace=dict(result.trace),
            )
            self._events.append(event)
            self._next_sequence += 1
            return event

    def snapshot(
        self, *, after_sequence: int = 0, limit: int = 100
    ) -> tuple[DashboardEvent, ...]:
        bounded_limit = max(1, min(limit, 500))
        with self._lock:
            matches = [
                event for event in self._events if event.sequence > after_sequence
            ]
            return tuple(matches[-bounded_limit:])

    @property
    def latest_sequence(self) -> int:
        with self._lock:
            return self._next_sequence - 1

    def restore(self, events: list[DashboardEvent]) -> None:
        """Restore a bounded, monotonically sequenced diagnostic tail."""
        ordered = sorted(events, key=lambda event: event.sequence)
        if len({event.sequence for event in ordered}) != len(ordered):
            raise ValueError("dashboard event sequences must be unique")
        with self._lock:
            capacity = self._events.maxlen or 500
            self._events = deque(ordered[-capacity:], maxlen=capacity)
            self._next_sequence = (ordered[-1].sequence + 1) if ordered else 1
