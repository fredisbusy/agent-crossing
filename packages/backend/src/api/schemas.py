from pydantic import BaseModel, Field


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
    plan_diagnostics: dict[str, object] = Field(default_factory=dict)
    parse_failure_rate: float
    silent_rate: float
    semantic_repeat_rate: float
    topic_progress_rate: float


class WorldSchedulerResponse(BaseModel):
    running: bool
    turn: int
    current_time: str
    tick_interval_seconds: float
