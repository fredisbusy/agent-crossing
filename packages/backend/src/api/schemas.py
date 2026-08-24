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
