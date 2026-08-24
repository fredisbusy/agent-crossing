from typing import Literal

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    version: str


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
    revision: int
    map_id: str
    agents: list[SpatialAgentResponse]
    current_time: str | None
    turn: int
    scheduler_running: bool


class DashboardMemoryResponse(BaseModel):
    id: int
    node_type: Literal["OBSERVATION", "REFLECTION", "PLAN"]
    citations: list[int] | None
    content: str
    created_at: str
    last_accessed_at: str
    importance: int


class DashboardReflectionStatusResponse(BaseModel):
    accumulated_importance: int
    threshold: int


class DashboardAgentResponse(BaseModel):
    agent_id: str
    name: str
    current_action: str
    destination: str | None
    tile_position: WorldMapPointResponse
    route_remaining: int
    bubble_kind: Literal["speech", "thought", "action"]
    bubble_text: str
    current_plan_context: list[str]
    active_day: PlanItemResponse | None
    active_hourly: PlanItemResponse | None
    active_minute: PlanItemResponse | None
    day_plan: list[PlanItemResponse]
    reflection_status: DashboardReflectionStatusResponse
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
    thought: str
    model_thought: str
    self_critique: str
    decision_reason: str
    action_summary: str
    decision_process: dict[str, object]
    governance_trace: dict[str, object]


class DashboardWorldResponse(BaseModel):
    available: bool
    revision: int
    turn: int
    current_time: str | None
    scheduler_running: bool
    cognitive_active: bool
    effective_time_step_seconds: int
    cognitive_runtime_error: str | None


class DashboardStateResponse(BaseModel):
    world: DashboardWorldResponse
    agents: list[DashboardAgentResponse]
    events: list[DashboardEventResponse]
    latest_sequence: int
