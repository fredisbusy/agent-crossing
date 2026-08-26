from typing import Literal

from agents.relationships import RelationshipEventType
from pydantic import BaseModel, Field, field_validator


class StatusResponse(BaseModel):
    status: str
    version: str


class SessionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session name must not be blank")
        return normalized


class SessionSaveRequest(BaseModel):
    expected_save_version: int | None = Field(default=None, gt=0)


class SessionSummaryResponse(BaseModel):
    id: str
    name: str
    status: Literal["ACTIVE", "SAVED", "ERROR"]
    map_id: str
    world_time: str
    turn: int
    revision: int
    save_version: int
    created_at: str
    saved_at: str


class SessionListResponse(BaseModel):
    current_session_id: str | None
    sessions: list[SessionSummaryResponse]


class WorldStateResponse(BaseModel):
    available: bool
    turn: int
    current_time: str
    history_size: int
    agent_names: list[str]
    scheduler_running: bool
    tick_interval_seconds: float
    cognitive_active: bool
    effective_time_step_seconds: int


class WorldStepResponse(BaseModel):
    turn: int
    speaker_name: str
    reply: str
    silent_reason: str
    trace: dict[str, object]
    parse_failure_rate: float
    silent_rate: float
    semantic_repeat_rate: float
    topic_progress_rate: float


class WorldSchedulerResponse(BaseModel):
    running: bool
    turn: int
    current_time: str
    tick_interval_seconds: float
    cognitive_active: bool
    effective_time_step_seconds: int


class WorldMapPointResponse(BaseModel):
    x: int
    y: int


class WorldMapBoundsResponse(WorldMapPointResponse):
    width: int
    height: int


class WorldMapLocationResponse(BaseModel):
    id: str
    name: str
    kind: str
    location_path: str
    color: str
    bounds: WorldMapBoundsResponse


class WorldMapInteractableResponse(BaseModel):
    id: str
    name: str
    kind: str
    location_path: str
    affordances: list[str]
    position: WorldMapPointResponse


class WorldMapSpawnResponse(BaseModel):
    id: str
    agent_id: str
    color: str
    position: WorldMapPointResponse


class WorldMapResponse(BaseModel):
    id: str
    name: str
    width: int
    height: int
    tile_width: int
    tile_height: int
    locations: list[WorldMapLocationResponse]
    collisions: list[WorldMapBoundsResponse]
    interactables: list[WorldMapInteractableResponse]
    spawns: list[WorldMapSpawnResponse]


class WorldObserveRequest(BaseModel):
    position: WorldMapPointResponse
    radius: int = 96


class WorldObservationResponse(BaseModel):
    location_path: str
    nearby_interactables: list[WorldMapInteractableResponse]


class GodModePerceptionRequest(BaseModel):
    """§3.2 User Controls / §8.1 God mode: injects an arbitrary natural-language
    perception event into the world as an observation for a single agent
    (e.g. "Isabella's apartment: kitchen: stove is burning"). This is
    environment-state injection, not an "inner voice"/directive input
    (SPEC.md §3.1.2) — the agent still decides how to react to it.
    """

    agent_id: str
    content: str


class GodModePerceptionResponse(BaseModel):
    agent_id: str
    memory_id: int
    created_at: str


class WorldPathRequest(BaseModel):
    start: WorldMapPointResponse
    goal: WorldMapPointResponse


class WorldPathResponse(BaseModel):
    reachable: bool
    path: list[WorldMapPointResponse]


class SpatialAgentResponse(BaseModel):
    agent_id: str
    name: str
    tile_position: WorldMapPointResponse
    position: WorldMapPointResponse
    destination: str | None
    current_action: str
    plan: str
    route_remaining: int
    active_day: "PlanItemResponse | None"
    active_hourly: "PlanItemResponse | None"
    active_minute: "PlanItemResponse | None"
    day_plan: list["PlanItemResponse"]
    bubble_kind: Literal["speech", "thought", "action"]
    bubble_text: str


class PlanItemResponse(BaseModel):
    start_time: str
    end_time: str
    location: str
    action_content: str


class SpatialWorldResponse(BaseModel):
    session_id: str | None
    revision: int
    map_id: str
    agents: list[SpatialAgentResponse]
    current_time: str | None
    turn: int
    scheduler_running: bool
    planning_error: str | None


class DashboardMemoryResponse(BaseModel):
    id: int
    node_type: Literal["OBSERVATION", "REFLECTION", "PLAN"]
    citations: list[int] | None
    content: str
    created_at: str
    last_accessed_at: str
    importance: int


class DashboardMemoryPageResponse(BaseModel):
    items: list[DashboardMemoryResponse]
    total: int = Field(ge=0)
    filtered_total: int = Field(ge=0)
    has_more: bool
    next_cursor: int | None
    snapshot_memory_max_id: int | None


class DashboardReflectionStatusResponse(BaseModel):
    accumulated_importance: int
    threshold: int
    reflection_total: int = Field(ge=0)
    last_reflection_at: str | None


class DashboardRelationshipEvidenceResponse(BaseModel):
    source: Literal["persona", "memory"]
    content: str
    memory_id: int | None
    node_type: Literal["OBSERVATION", "REFLECTION", "PLAN"] | None
    importance: int | None
    created_at: str | None


class DashboardRelationshipMetricsResponse(BaseModel):
    familiarity: int = Field(ge=0, le=100)
    trust: int = Field(ge=-100, le=100)
    affinity: int = Field(ge=-100, le=100)
    tension: int = Field(ge=0, le=100)
    romantic_interest: int = Field(ge=0, le=100)


class DashboardRelationshipEventResponse(BaseModel):
    id: str
    event_type: RelationshipEventType
    occurred_at: str
    familiarity_delta: int = Field(ge=-100, le=100)
    trust_delta: int = Field(ge=-100, le=100)
    affinity_delta: int = Field(ge=-100, le=100)
    tension_delta: int = Field(ge=-100, le=100)
    romantic_interest_delta: int = Field(ge=-100, le=100)
    rule_version: Literal["relationship-v1"]


class DashboardRelationshipResponse(BaseModel):
    target_agent_id: str
    target_name: str
    measurement: Literal["modeled_v1"]
    metrics: DashboardRelationshipMetricsResponse
    status_label: Literal[
        "긴장된 관계",
        "불신하는 관계",
        "거리감 있는 관계",
        "아직 낯선 사이",
        "가깝고 신뢰하는 관계",
        "인간적으로 호감 있는 관계",
        "신뢰하는 관계",
        "알아가는 관계",
    ]
    revision: int = Field(ge=0)
    updated_at: str | None
    last_interaction_at: str | None
    summary: str | None
    summary_status: Literal["available", "no_explicit_evidence"]
    evidence_total: int = Field(ge=0)
    has_more_evidence: bool
    recent_events: list[DashboardRelationshipEventResponse]
    evidence: list[DashboardRelationshipEvidenceResponse]


class DashboardAgentResponse(BaseModel):
    agent_id: str
    name: str
    age: int = Field(ge=0)
    gender: str = Field(min_length=1)
    traits: list[str]
    persona: list[str]
    current_action: str
    destination: str | None
    current_location_path: str | None
    current_location_source: Literal["map", "arrival", "interior", "unknown"]
    tile_position: WorldMapPointResponse
    route_remaining: int
    bubble_kind: Literal["speech", "thought", "action"]
    bubble_text: str
    current_plan_context: list[str]
    active_day: PlanItemResponse | None
    active_hourly: PlanItemResponse | None
    active_minute: PlanItemResponse | None
    day_plan: list[PlanItemResponse]
    last_replan_reason: str | None
    memory_total: int = Field(ge=0)
    memory_has_more: bool
    reflection_status: DashboardReflectionStatusResponse
    relationships: list[DashboardRelationshipResponse]
    memories: list[DashboardMemoryResponse]


class DashboardEventResponse(BaseModel):
    sequence: int
    turn: int
    occurred_at: str
    agent_id: str
    agent_name: str
    reply: str
    silent_reason: str
    parse_failure: bool
    decision_reason: str
    action_summary: str


class DashboardWorldResponse(BaseModel):
    available: bool
    revision: int
    turn: int
    current_time: str | None
    scheduler_running: bool
    cognitive_active: bool
    effective_time_step_seconds: int
    cognitive_runtime_error: str | None
    planning_error: str | None
    snapshot_generated_at: str


class DashboardStateResponse(BaseModel):
    world: DashboardWorldResponse
    agents: list[DashboardAgentResponse]
    events: list[DashboardEventResponse]
    oldest_sequence: int = Field(ge=0)
    latest_sequence: int
