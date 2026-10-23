from pydantic import BaseModel
from world.contracts import WorldSnapshot


class StatusResponse(BaseModel):
    status: str
    version: str


class WorldStateResponse(BaseModel):
    snapshot: WorldSnapshot
    scheduler_running: bool
    tick_interval_seconds: float


class WorldSchedulerResponse(BaseModel):
    running: bool
    tick: int
    tick_interval_seconds: float
