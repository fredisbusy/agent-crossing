import logging
from pathlib import Path
from typing import cast

from agents.persona_loader import PersonaLoader
from api.schemas import (
    SpatialAgentResponse,
    SpatialWorldResponse,
    StatusResponse,
    WorldMapBoundsResponse,
    WorldMapInteractableResponse,
    WorldMapLocationResponse,
    WorldMapPointResponse,
    WorldMapResponse,
    WorldMapSpawnResponse,
    WorldObservationResponse,
    WorldObserveRequest,
    WorldPathRequest,
    WorldPathResponse,
    WorldSchedulerResponse,
    WorldStateResponse,
    WorldStepResponse,
)
from db import init_db
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from settings import (
    EMBEDDING_MODEL,
    GOOGLE_AI_STUDIO_API_KEY,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
    WORLD_TICK_INTERVAL_SECONDS,
)
from world.runtime import WorldRuntime, WorldRuntimeConfig, build_world_runtime
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime, SpatialWorldSnapshot
from world.stream import SpatialWorldStream
from world.world_map import MapBounds, MapPoint, WorldMap, load_world_map

app = FastAPI(title="Agent Crossing API")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup() -> None:
    persona_dir = Path(__file__).resolve().parents[2] / "persona"
    app.state.persona_loader = PersonaLoader(persona_dir)
    app.state.agent_personas = app.state.persona_loader.load_all()
    app.state.spatial_runtime = SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(
                agent_id=persona.agent.id,
                name=persona.agent.name,
                plan_context=tuple(persona.current_plan_context),
            )
            for persona in app.state.agent_personas
        ],
    )
    app.state.spatial_stream = SpatialWorldStream(runtime=app.state.spatial_runtime)
    await app.state.spatial_stream.start()
    persona_names = [persona.agent.id for persona in app.state.agent_personas]
    app.state.world_runtime = None
    app.state.cognitive_runtime_error = None
    try:
        init_db()
        if len(persona_names) >= 2:
            app.state.world_runtime = build_world_runtime(
                config=WorldRuntimeConfig(
                    agent_persona_names=persona_names[:2],
                    base_url=LLM_BASE_URL,
                    api_key=LLM_API_KEY or GOOGLE_AI_STUDIO_API_KEY,
                    llm_model=LLM_MODEL,
                    embedding_model=EMBEDDING_MODEL,
                    timeout_seconds=LLM_TIMEOUT_SECONDS,
                    persona_dir=str(persona_dir),
                    tick_interval_seconds=WORLD_TICK_INTERVAL_SECONDS,
                )
            )
    except Exception as error:
        app.state.cognitive_runtime_error = str(error)
        logger.exception(
            "Cognitive runtime is unavailable; spatial world remains active"
        )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    spatial_stream = cast(
        SpatialWorldStream | None,
        getattr(app.state, "spatial_stream", None),
    )
    if spatial_stream is not None:
        await spatial_stream.stop()
    runtime = cast(WorldRuntime | None, getattr(app.state, "world_runtime", None))
    if runtime is not None:
        await runtime.stop_scheduler()


@app.get("/", response_model=StatusResponse)
async def get_status():
    return {"status": "online", "version": "0.1.0"}


@app.get("/world/map", response_model=WorldMapResponse)
async def get_world_map() -> WorldMapResponse:
    world_map = load_world_map()
    return _world_map_response(world_map)


def _world_map_response(world_map: WorldMap) -> WorldMapResponse:
    return WorldMapResponse(
        id=world_map.id,
        name=world_map.name,
        width=world_map.width,
        height=world_map.height,
        tile_width=world_map.tile_width,
        tile_height=world_map.tile_height,
        locations=[
            WorldMapLocationResponse(
                id=location.id,
                name=location.name,
                kind=location.kind,
                location_path=location.location_path,
                color=location.color,
                bounds=_map_bounds_response(location.bounds),
            )
            for location in world_map.locations
        ],
        collisions=[_map_bounds_response(bounds) for bounds in world_map.collisions],
        interactables=[
            WorldMapInteractableResponse(
                id=item.id,
                name=item.name,
                kind=item.kind,
                location_path=item.location_path,
                affordances=list(item.affordances),
                position=_map_point_response(item.position),
            )
            for item in world_map.interactables
        ],
        spawns=[
            WorldMapSpawnResponse(
                id=spawn.id,
                agent_id=spawn.agent_id,
                color=spawn.color,
                position=_map_point_response(spawn.position),
            )
            for spawn in world_map.spawns
        ],
    )


def _map_point_response(point: MapPoint) -> WorldMapPointResponse:
    return WorldMapPointResponse(x=point.x, y=point.y)


def _map_bounds_response(bounds: MapBounds) -> WorldMapBoundsResponse:
    return WorldMapBoundsResponse(
        x=bounds.x,
        y=bounds.y,
        width=bounds.width,
        height=bounds.height,
    )


def _require_spatial_runtime() -> SpatialWorldRuntime:
    runtime = cast(
        SpatialWorldRuntime | None,
        getattr(app.state, "spatial_runtime", None),
    )
    if runtime is None:
        raise HTTPException(
            status_code=503, detail="spatial runtime is not initialized"
        )
    return runtime


def _require_spatial_stream() -> SpatialWorldStream:
    stream = cast(
        SpatialWorldStream | None,
        getattr(app.state, "spatial_stream", None),
    )
    if stream is None:
        raise HTTPException(status_code=503, detail="spatial stream is not initialized")
    return stream


def _spatial_response(snapshot: SpatialWorldSnapshot) -> SpatialWorldResponse:
    return SpatialWorldResponse(
        revision=snapshot.revision,
        map_id=snapshot.map_id,
        agents=[
            SpatialAgentResponse(
                agent_id=agent.agent_id,
                name=agent.name,
                tile_position=_map_point_response(agent.tile_position),
                position=_map_point_response(agent.pixel_position),
                destination=agent.destination,
                current_action=agent.current_action,
                plan=agent.plan,
                route_remaining=agent.route_remaining,
            )
            for agent in snapshot.agents
        ],
    )


@app.get("/world/spatial/state", response_model=SpatialWorldResponse)
async def get_world_spatial_state() -> SpatialWorldResponse:
    return _spatial_response(_require_spatial_runtime().snapshot())


@app.post("/world/spatial/step", response_model=SpatialWorldResponse)
async def post_world_spatial_step() -> SpatialWorldResponse:
    return _spatial_response(_require_spatial_runtime().tick())


@app.websocket("/ws/world")
async def world_websocket(websocket: WebSocket) -> None:
    stream = _require_spatial_stream()
    await websocket.accept()
    queue = stream.subscribe()
    try:
        while True:
            snapshot = await queue.get()
            await websocket.send_json(_spatial_response(snapshot).model_dump())
    except WebSocketDisconnect:
        pass
    finally:
        stream.unsubscribe(queue)


@app.post("/world/observe", response_model=WorldObservationResponse)
async def post_world_observe(request: WorldObserveRequest) -> WorldObservationResponse:
    world_map = load_world_map()
    position = MapPoint(x=request.position.x, y=request.position.y)
    location = world_map.location_at(position)
    nearby = [
        item
        for item in world_map.interactables
        if ((item.position.x - position.x) ** 2 + (item.position.y - position.y) ** 2)
        <= request.radius**2
    ]
    return WorldObservationResponse(
        location_path=location.location_path if location else world_map.name,
        nearby_interactables=[
            WorldMapInteractableResponse(
                id=item.id,
                name=item.name,
                kind=item.kind,
                location_path=item.location_path,
                affordances=list(item.affordances),
                position=_map_point_response(item.position),
            )
            for item in nearby
        ],
    )


@app.post("/world/path", response_model=WorldPathResponse)
async def post_world_path(request: WorldPathRequest) -> WorldPathResponse:
    world_map = load_world_map()
    path = world_map.find_path(
        MapPoint(x=request.start.x, y=request.start.y),
        MapPoint(x=request.goal.x, y=request.goal.y),
    )
    return WorldPathResponse(
        reachable=bool(path),
        path=[WorldMapPointResponse(x=point.x, y=point.y) for point in path],
    )


def _require_runtime() -> WorldRuntime:
    runtime = cast(WorldRuntime | None, app.state.world_runtime)
    if runtime is None:
        raise HTTPException(status_code=503, detail="world runtime is not initialized")
    return runtime


@app.get("/world/state", response_model=WorldStateResponse)
async def get_world_state() -> WorldStateResponse:
    runtime = _require_runtime()
    state = runtime.state()
    return WorldStateResponse(
        available=True,
        turn=state.turn,
        current_time=state.current_time.isoformat(),
        history_size=state.history_size,
        agent_names=[agent.name for agent in runtime.agents],
        scheduler_running=state.scheduler_running,
        tick_interval_seconds=state.tick_interval_seconds,
    )


@app.post("/world/step", response_model=WorldStepResponse)
async def post_world_step() -> WorldStepResponse:
    runtime = _require_runtime()
    step_result = runtime.step()
    metrics = runtime.metrics()
    return WorldStepResponse(
        turn=runtime.turn,
        speaker_name=step_result.speaker_name,
        reply=step_result.reply,
        silent_reason=step_result.silent_reason,
        trace=step_result.trace,
        parse_failure_rate=metrics.parse_failure_rate,
        silent_rate=metrics.silent_rate,
        semantic_repeat_rate=metrics.semantic_repeat_rate,
        topic_progress_rate=metrics.topic_progress_rate,
    )


def _scheduler_response(runtime: WorldRuntime) -> WorldSchedulerResponse:
    state = runtime.state()
    return WorldSchedulerResponse(
        running=state.scheduler_running,
        turn=state.turn,
        current_time=state.current_time.isoformat(),
        tick_interval_seconds=state.tick_interval_seconds,
    )


@app.post("/world/tick/start", response_model=WorldSchedulerResponse)
async def post_world_tick_start() -> WorldSchedulerResponse:
    runtime = _require_runtime()
    await runtime.start_scheduler()
    return _scheduler_response(runtime)


@app.post("/world/tick/stop", response_model=WorldSchedulerResponse)
async def post_world_tick_stop() -> WorldSchedulerResponse:
    runtime = _require_runtime()
    await runtime.stop_scheduler()
    return _scheduler_response(runtime)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
