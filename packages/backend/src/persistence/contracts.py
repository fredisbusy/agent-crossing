from __future__ import annotations

import datetime
import math
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from settings import EMBEDDING_DIMENSION

SNAPSHOT_SCHEMA_VERSION = 4


class PointSave(BaseModel):
    x: int
    y: int


class PlanItemSave(BaseModel):
    start_time: datetime.datetime
    end_time: datetime.datetime
    location: str
    action_content: str


class PlanningStateSave(BaseModel):
    plan_date: datetime.date | None
    day_items: list[PlanItemSave]
    hourly_items: list[PlanItemSave]
    minute_items: list[PlanItemSave]
    hourly_parent_key: tuple[datetime.datetime, datetime.datetime] | None
    minute_parent_key: tuple[datetime.datetime, datetime.datetime] | None
    last_replan_reason: str


class MemorySave(BaseModel):
    id: int
    node_type: Literal["OBSERVATION", "REFLECTION", "PLAN"]
    citations: list[int] | None
    content: str
    created_at: datetime.datetime
    last_accessed_at: datetime.datetime
    importance: int = Field(ge=1, le=10)
    embedding: list[float]

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, value: list[float]) -> list[float]:
        if len(value) != EMBEDDING_DIMENSION:
            raise ValueError(f"embedding must contain {EMBEDDING_DIMENSION} dimensions")
        if not all(math.isfinite(component) for component in value):
            raise ValueError("embedding must contain only finite values")
        return value


class CharacterMovementSave(BaseModel):
    tile_position: PointSave
    goal: PointSave | None
    route: list[PointSave]
    destination_path: str | None
    explicit_location: str | None
    current_action: str
    plan: str
    cognitive_kind: Literal["speech", "thought"] | None
    cognitive_text: str


class CharacterSave(CharacterMovementSave):
    agent_id: str
    name: str
    age: int
    traits: list[str]
    identity_stable_set: list[str]
    lifestyle_and_routine: list[str]
    current_plan_context: list[str]
    reflection_accumulated_importance: int = Field(ge=0)
    memories: list[MemorySave]
    planning: PlanningStateSave | None


class ConversationSave(BaseModel):
    participant_agent_names: tuple[str, str]
    is_active: bool
    turn_index: int = Field(ge=0)
    dialogue_turn_window: int | None
    dialogue_target_turns: int = Field(ge=2)
    dialogue_turns_taken: int = Field(ge=0)
    dialogue_goal: str | None
    history: list[tuple[str, str]]
    dialogue_history_by_agent: dict[str, list[tuple[str, str]]]
    incoming_utterances_by_agent: dict[str, list[str]]


class PositionHistorySave(BaseModel):
    """One recorded tile-position change (§ replay/reconstruction).

    Only appended when an agent's tile position (or destination/action)
    actually changes — see `world.spatial.PositionHistoryBuffer` — not on
    every real-time world tick.
    """

    agent_id: str
    turn: int = Field(ge=0)
    occurred_at: datetime.datetime
    tile_position: PointSave
    destination_path: str | None
    current_action: str


class DashboardEventSave(BaseModel):
    sequence: int = Field(gt=0)
    turn: int = Field(ge=0)
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


class RelationshipMetricsSave(BaseModel):
    familiarity: int = Field(ge=0, le=100)
    trust: int = Field(ge=-100, le=100)
    affinity: int = Field(ge=-100, le=100)
    tension: int = Field(ge=0, le=100)
    romantic_interest: int = Field(default=0, ge=0, le=100)


class RelationshipDeltaSave(BaseModel):
    familiarity: int
    trust: int
    affinity: int
    tension: int
    romantic_interest: int = 0


class RelationshipStateSave(BaseModel):
    subject_agent_id: str
    target_agent_id: str
    metrics: RelationshipMetricsSave
    last_interaction_at: datetime.datetime | None
    updated_at: datetime.datetime | None
    revision: int = Field(ge=0)


class RelationshipEventSave(BaseModel):
    id: str
    source_event_id: str
    subject_agent_id: str
    target_agent_id: str
    event_type: Literal[
        "DIALOGUE_COMPLETED",
        "HELP_GIVEN",
        "HELP_RECEIVED",
        "PERSONAL_DISCLOSURE_RECEIVED",
        "COMPLIMENT_RECEIVED",
        "PROMISE_MADE",
        "PROMISE_KEPT",
        "PROMISE_BROKEN",
        "CONFLICT",
        "INSULT_RECEIVED",
        "APOLOGY_ACCEPTED",
        "ROMANTIC_INTEREST_RECOGNIZED",
        "ROMANTIC_GESTURE_WELCOMED",
        "ROMANTIC_BOUNDARY_SET",
    ]
    occurred_at: datetime.datetime
    requested_delta: RelationshipDeltaSave
    applied_delta: RelationshipDeltaSave
    before: RelationshipMetricsSave
    after: RelationshipMetricsSave
    rule_version: Literal["relationship-v1"]
    source_kind: Literal["runtime", "dialogue", "action", "persona"]

    @field_validator("id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class RuntimeSaveState(BaseModel):
    schema_version: Literal[3, 4] = SNAPSHOT_SCHEMA_VERSION
    map_id: str
    current_time: datetime.datetime
    turn: int = Field(ge=0)
    revision: int = Field(ge=0)
    parse_failures: int = Field(ge=0)
    silent_turns: int = Field(ge=0)
    scheduler_was_running: bool
    planning_error: str | None
    # 조우 쌍(pair)별 마지막 대화 종료/패스바이 시각. N-agent 확장 이전에는
    # 마을 전체가 하나의 전역 쿨다운을 공유했지만, 이제 쌍마다 독립적으로
    # 쿨다운을 추적한다. 키는 `world.runtime._pair_key`와 동일한 형식
    # (두 agent_id를 정렬해 "|"로 이은 문자열).
    pair_cooldown_until: dict[str, datetime.datetime]
    # 동시에 여러 쌍이 대화 중일 수 있다(§3.4) — 활성 세션마다 하나씩.
    conversations: list[ConversationSave]
    characters: list[CharacterSave]
    dashboard_events: list[DashboardEventSave]
    # Optional/defaulted so snapshots saved before this field existed still
    # validate (`Repository.latest_session()` loads old rows via
    # `RuntimeSaveState.model_validate(record.snapshot)`).
    position_history: list[PositionHistorySave] = Field(default_factory=list)
    # v4: session-scoped directional relationship state and its auditable ledger.
    # Defaults keep v3 snapshots loadable; the runtime seeds their neutral pairs.
    relationship_states: list[RelationshipStateSave] = Field(default_factory=list)
    relationship_events: list[RelationshipEventSave] = Field(default_factory=list)
    relationship_event_namespace: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Old v4 snapshots may have acquired a namespace after their event IDs were
    # generated. New exports set this marker only when IDs and namespace agree.
    relationship_event_ids_verified: bool = False

    @model_validator(mode="after")
    def validate_relationship_snapshot(self) -> "RuntimeSaveState":
        uuid.UUID(self.relationship_event_namespace)
        if self.schema_version == 3:
            return self
        roster = {character.agent_id for character in self.characters}
        expected_pairs = {
            (subject, target)
            for subject in roster
            for target in roster
            if subject != target
        }
        actual_pairs = [
            (state.subject_agent_id, state.target_agent_id)
            for state in self.relationship_states
        ]
        if (
            len(actual_pairs) != len(set(actual_pairs))
            or set(actual_pairs) != expected_pairs
        ):
            raise ValueError("v4 relationship states must cover every directional pair")
        if len(self.relationship_events) > 10_000:
            raise ValueError("relationship event ledger exceeds session limit")
        if any(
            (event.subject_agent_id, event.target_agent_id) not in expected_pairs
            for event in self.relationship_events
        ):
            raise ValueError("relationship event references an unknown pair")
        return self


_PRIVATE_TRACE_KEYS = {
    "api_key",
    "authorization",
    "prompt",
    "raw_prompt",
    "raw_response",
    "system_prompt",
}


def sanitized_diagnostics(value: object, *, depth: int = 0) -> object:
    """Bound persisted diagnostics and remove provider/private payloads."""
    if depth >= 6:
        return "[depth-limited]"
    if isinstance(value, str):
        return value[:8192]
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for raw_key, item in list(value.items())[:100]:
            key = str(raw_key)
            if key.lower() in _PRIVATE_TRACE_KEYS:
                continue
            result[key] = sanitized_diagnostics(item, depth=depth + 1)
        return result
    if isinstance(value, list | tuple):
        return [sanitized_diagnostics(item, depth=depth + 1) for item in value[:100]]
    return str(value)[:8192]
