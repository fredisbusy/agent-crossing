import logging
from pathlib import Path
from typing import cast
import asyncio
import uuid

from agents.persona_loader import PersonaLoader
from agents.planning.lifecycle import PlanItemSnapshot
from agents.relationship_diagnostics import build_relationship_snapshot
from api.schemas import (
    DashboardAgentResponse,
    DashboardEventResponse,
    DashboardMemoryResponse,
    DashboardReflectionStatusResponse,
    DashboardRelationshipEvidenceResponse,
    DashboardRelationshipResponse,
    DashboardStateResponse,
    DashboardWorldResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionSaveRequest,
    SessionSummaryResponse,
    SpatialAgentResponse,
    PlanItemResponse,
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
    WORLD_COGNITIVE_TIME_STEP_SECONDS,
)
from world.runtime import WorldRuntime, WorldRuntimeConfig, build_world_runtime
from world.observability import DashboardEvent
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime, SpatialWorldSnapshot
from world.stream import SpatialWorldStream
from world.world_map import MapBounds, MapPoint, WorldMap, load_world_map
from persistence.repository import (
    GameSessionRepository,
    SaveVersionConflictError,
    SessionSummary,
)

app = FastAPI(title="Agent Crossing API")
logger = logging.getLogger(__name__)


def _runtime_config(*, persona_dir: Path, persona_names: list[str]) -> WorldRuntimeConfig:
    return WorldRuntimeConfig(
        agent_persona_names=persona_names[:2],
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY or GOOGLE_AI_STUDIO_API_KEY,
        llm_model=LLM_MODEL,
        embedding_model=EMBEDDING_MODEL,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        persona_dir=str(persona_dir),
        tick_interval_seconds=WORLD_TICK_INTERVAL_SECONDS,
        cognitive_time_step_seconds=WORLD_COGNITIVE_TIME_STEP_SECONDS,
    )


def _build_runtime_bundle() -> tuple[WorldRuntime, SpatialWorldRuntime]:
    persona_names = cast(list[str], app.state.persona_names)
    persona_dir = cast(Path, app.state.persona_dir)
    spatial_runtime = SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(
                agent_id=persona.agent.id,
                name=persona.agent.name,
                plan_context=(),
            )
            for persona in app.state.agent_personas
        ],
    )
    runtime = build_world_runtime(
        config=_runtime_config(persona_dir=persona_dir, persona_names=persona_names),
        spatial_runtime=spatial_runtime,
    )
    return runtime, spatial_runtime


@app.on_event("startup")
async def on_startup() -> None:
    persona_dir = Path(__file__).resolve().parents[2] / "persona"
    app.state.persona_dir = persona_dir
    app.state.persona_loader = PersonaLoader(persona_dir)
    app.state.agent_personas = app.state.persona_loader.load_all()
    persona_names = [persona.agent.id for persona in app.state.agent_personas]
    app.state.persona_names = persona_names
    app.state.session_lock = asyncio.Lock()
    app.state.session_repository = None
    app.state.current_session_id = None
    app.state.world_runtime = None
    app.state.cognitive_runtime_error = None
    try:
        init_db()
        if len(persona_names) >= 2:
            repository = GameSessionRepository()
            app.state.session_repository = repository
            runtime, spatial_runtime = await asyncio.to_thread(_build_runtime_bundle)
            latest = await asyncio.to_thread(repository.latest_session)
            should_start_scheduler = True
            if latest is not None:
                summary, saved_state = latest
                runtime.restore_save_state(saved_state)
                activated = await asyncio.to_thread(
                    repository.activate, session_id=summary.id
                )
                if activated is None:
                    raise RuntimeError("saved session disappeared during startup")
                app.state.current_session_id = summary.id
                should_start_scheduler = saved_state.scheduler_was_running
            else:
                initial_state = runtime.export_save_state(scheduler_was_running=True)
                summary = await asyncio.to_thread(
                    repository.create,
                    name="브라이어 코브 1",
                    state=initial_state,
                )
                app.state.current_session_id = summary.id
            app.state.world_runtime = runtime
            app.state.spatial_runtime = spatial_runtime
            app.state.spatial_stream = SpatialWorldStream(runtime=spatial_runtime)
            await app.state.spatial_stream.start()
            if should_start_scheduler:
                await runtime.start_scheduler()
    except Exception as error:
        app.state.cognitive_runtime_error = str(error)
        logger.exception(
            "Cognitive runtime is unavailable; spatial world remains active"
        )
    if getattr(app.state, "spatial_runtime", None) is None:
        spatial_runtime = SpatialWorldRuntime(
            world_map=load_world_map(),
            seeds=[
                SpatialAgentSeed(
                    agent_id=persona.agent.id,
                    name=persona.agent.name,
                    plan_context=(),
                )
                for persona in app.state.agent_personas
            ],
        )
        app.state.spatial_runtime = spatial_runtime
        app.state.spatial_stream = SpatialWorldStream(runtime=spatial_runtime)
        await app.state.spatial_stream.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    spatial_stream = cast(
        SpatialWorldStream | None,
        getattr(app.state, "spatial_stream", None),
    )
    runtime = cast(WorldRuntime | None, getattr(app.state, "world_runtime", None))
    if runtime is not None:
        repository = cast(
            GameSessionRepository | None,
            getattr(app.state, "session_repository", None),
        )
        current_session_id = cast(
            uuid.UUID | None, getattr(app.state, "current_session_id", None)
        )
        was_running = runtime.scheduler_running
        if spatial_stream is not None:
            await spatial_stream.stop()
        try:
            await runtime.pause_scheduler()
            if repository is not None and current_session_id is not None:
                state = runtime.export_save_state(
                    scheduler_was_running=was_running
                )
                await asyncio.to_thread(
                    repository.save,
                    session_id=current_session_id,
                    state=state,
                    expected_save_version=None,
                )
        except Exception:
            logger.exception("Failed to save the active session during shutdown")
        await runtime.stop_scheduler()
    elif spatial_stream is not None:
        await spatial_stream.stop()


@app.get("/", response_model=StatusResponse)
async def get_status():
    return {"status": "online", "version": "0.1.0"}


def _require_session_repository() -> GameSessionRepository:
    repository = cast(
        GameSessionRepository | None,
        getattr(app.state, "session_repository", None),
    )
    if repository is None:
        raise HTTPException(status_code=503, detail="session database is unavailable")
    return repository


def _session_summary_response(summary: SessionSummary) -> SessionSummaryResponse:
    return SessionSummaryResponse(
        id=str(summary.id),
        name=summary.name,
        status=summary.status.value,
        map_id=summary.map_id,
        world_time=summary.world_time.isoformat(),
        turn=summary.turn,
        revision=summary.revision,
        save_version=summary.save_version,
        created_at=summary.created_at.isoformat(),
        saved_at=summary.saved_at.isoformat(),
    )


async def _resume_runtime(
    *, runtime: WorldRuntime, stream: SpatialWorldStream, should_run: bool
) -> None:
    if not stream.running:
        await stream.start()
    if should_run and not runtime.scheduler_running:
        await runtime.start_scheduler()


@app.get("/sessions", response_model=SessionListResponse)
async def get_sessions() -> SessionListResponse:
    repository = _require_session_repository()
    summaries = await asyncio.to_thread(repository.list_sessions, limit=50)
    current_session_id = cast(
        uuid.UUID | None, getattr(app.state, "current_session_id", None)
    )
    return SessionListResponse(
        current_session_id=(str(current_session_id) if current_session_id else None),
        sessions=[_session_summary_response(summary) for summary in summaries],
    )


@app.post("/sessions", response_model=SessionSummaryResponse, status_code=201)
async def post_session(request: SessionCreateRequest) -> SessionSummaryResponse:
    repository = _require_session_repository()
    lock = cast(asyncio.Lock, app.state.session_lock)
    async with lock:
        new_runtime, new_spatial = await asyncio.to_thread(_build_runtime_bundle)
        new_state = new_runtime.export_save_state(scheduler_was_running=True)
        old_runtime = cast(WorldRuntime, _require_runtime())
        old_spatial = cast(SpatialWorldRuntime, app.state.spatial_runtime)
        old_session_id = cast(
            uuid.UUID | None, getattr(app.state, "current_session_id", None)
        )
        stream = cast(SpatialWorldStream, app.state.spatial_stream)
        old_was_running = old_runtime.scheduler_running
        await stream.stop()
        await old_runtime.pause_scheduler()
        try:
            await stream.replace_runtime(new_spatial)
            app.state.world_runtime = new_runtime
            app.state.spatial_runtime = new_spatial
            await stream.start()
            await new_runtime.start_scheduler()
            summary = await asyncio.to_thread(
                repository.create,
                name=request.name,
                state=new_state,
            )
            app.state.current_session_id = summary.id
        except Exception:
            await stream.stop()
            await new_runtime.pause_scheduler()
            await stream.replace_runtime(old_spatial)
            app.state.world_runtime = old_runtime
            app.state.spatial_runtime = old_spatial
            app.state.current_session_id = old_session_id
            await _resume_runtime(
                runtime=old_runtime,
                stream=stream,
                should_run=old_was_running,
            )
            raise
        return _session_summary_response(summary)


@app.post("/sessions/current/save", response_model=SessionSummaryResponse)
async def post_current_session_save(
    request: SessionSaveRequest,
) -> SessionSummaryResponse:
    repository = _require_session_repository()
    session_id = cast(
        uuid.UUID | None, getattr(app.state, "current_session_id", None)
    )
    if session_id is None:
        raise HTTPException(status_code=409, detail="there is no active session")
    lock = cast(asyncio.Lock, app.state.session_lock)
    async with lock:
        runtime = _require_runtime()
        stream = cast(SpatialWorldStream, app.state.spatial_stream)
        was_running = runtime.scheduler_running
        await stream.stop()
        await runtime.pause_scheduler()
        try:
            state = runtime.export_save_state(scheduler_was_running=was_running)
            summary = await asyncio.to_thread(
                repository.save,
                session_id=session_id,
                state=state,
                expected_save_version=request.expected_save_version,
            )
            if summary is None:
                raise HTTPException(status_code=404, detail="session not found")
        except SaveVersionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        finally:
            await _resume_runtime(
                runtime=runtime,
                stream=stream,
                should_run=was_running,
            )
        return _session_summary_response(summary)


@app.post("/sessions/{session_id}/load", response_model=SessionSummaryResponse)
async def post_session_load(session_id: uuid.UUID) -> SessionSummaryResponse:
    repository = _require_session_repository()
    saved = await asyncio.to_thread(repository.get, session_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="session not found")
    _, saved_state = saved
    new_runtime, new_spatial = await asyncio.to_thread(_build_runtime_bundle)
    new_runtime.restore_save_state(saved_state)
    lock = cast(asyncio.Lock, app.state.session_lock)
    async with lock:
        old_runtime = _require_runtime()
        old_spatial = cast(SpatialWorldRuntime, app.state.spatial_runtime)
        old_session_id = cast(
            uuid.UUID | None, getattr(app.state, "current_session_id", None)
        )
        stream = cast(SpatialWorldStream, app.state.spatial_stream)
        old_was_running = old_runtime.scheduler_running
        await stream.stop()
        await old_runtime.pause_scheduler()
        try:
            await stream.replace_runtime(new_spatial)
            app.state.world_runtime = new_runtime
            app.state.spatial_runtime = new_spatial
            await stream.start()
            if saved_state.scheduler_was_running:
                await new_runtime.start_scheduler()
            summary = await asyncio.to_thread(
                repository.activate, session_id=session_id
            )
            if summary is None:
                raise HTTPException(status_code=404, detail="session not found")
            app.state.current_session_id = session_id
        except Exception:
            await stream.stop()
            await new_runtime.pause_scheduler()
            await stream.replace_runtime(old_spatial)
            app.state.world_runtime = old_runtime
            app.state.spatial_runtime = old_spatial
            app.state.current_session_id = old_session_id
            await _resume_runtime(
                runtime=old_runtime,
                stream=stream,
                should_run=old_was_running,
            )
            raise
        return _session_summary_response(summary)


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
    def optional_plan_item(item: PlanItemSnapshot | None) -> PlanItemResponse | None:
        if item is None:
            return None
        return PlanItemResponse(
            start_time=item.start_time.isoformat(),
            end_time=item.end_time.isoformat(),
            location=item.location,
            action_content=item.action_content,
        )

    def plan_item(item: PlanItemSnapshot) -> PlanItemResponse:
        result = optional_plan_item(item)
        if result is None:
            raise ValueError("plan item must not be None")
        return result

    return SpatialWorldResponse(
        session_id=(
            str(current_session_id)
            if (
                current_session_id := getattr(
                    app.state, "current_session_id", None
                )
            )
            else None
        ),
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
                active_day=optional_plan_item(agent.active_day),
                active_hourly=optional_plan_item(agent.active_hourly),
                active_minute=optional_plan_item(agent.active_minute),
                day_plan=[plan_item(item) for item in agent.day_plan],
                bubble_kind=agent.bubble_kind,
                bubble_text=agent.bubble_text,
            )
            for agent in snapshot.agents
        ],
        current_time=(
            snapshot.current_time.isoformat() if snapshot.current_time else None
        ),
        turn=snapshot.turn,
        scheduler_running=snapshot.scheduler_running,
        planning_error=snapshot.planning_error,
    )


def _dashboard_plan_item(item: PlanItemSnapshot | None) -> PlanItemResponse | None:
    if item is None:
        return None
    return PlanItemResponse(
        start_time=item.start_time.isoformat(),
        end_time=item.end_time.isoformat(),
        location=item.location,
        action_content=item.action_content,
    )


def _public_diagnostics(value: object) -> object:
    """Remove provider payloads and secrets from public diagnostics responses."""
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return {
            key: _public_diagnostics(child)
            for key, child in mapping.items()
            if key not in {"raw_response", "prompt", "api_key"}
        }
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_public_diagnostics(child) for child in items]
    return value


def _dashboard_event_response(event: DashboardEvent) -> DashboardEventResponse:
    decision_process = _public_diagnostics(event.decision_process)
    governance_trace = _public_diagnostics(event.governance_trace)
    if not isinstance(decision_process, dict) or not isinstance(governance_trace, dict):
        raise ValueError("dashboard diagnostics must remain dictionaries")
    public_decision_process = cast(dict[str, object], decision_process)
    public_governance_trace = cast(dict[str, object], governance_trace)
    return DashboardEventResponse(
        sequence=event.sequence,
        turn=event.turn,
        occurred_at=event.occurred_at.isoformat(),
        agent_id=event.agent_id,
        agent_name=event.agent_name,
        reply=event.reply,
        silent_reason=event.silent_reason,
        parse_failure=event.parse_failure,
        thought=event.thought,
        model_thought=event.model_thought,
        self_critique=event.self_critique,
        decision_reason=event.decision_reason,
        action_summary=event.action_summary,
        decision_process=public_decision_process,
        governance_trace=public_governance_trace,
    )


def _dashboard_state_response(
    *, runtime: WorldRuntime, memory_limit: int, event_limit: int
) -> DashboardStateResponse:
    spatial = _require_spatial_runtime().snapshot()
    runtime_by_id = {str(agent.identity.id): agent for agent in runtime.agents}
    agents: list[DashboardAgentResponse] = []
    for spatial_agent in spatial.agents:
        runtime_agent = runtime_by_id.get(spatial_agent.agent_id)
        if runtime_agent is None:
            continue
        reflection = runtime_agent.brain.reflection_graph.reflection
        memories = runtime_agent.memory_service.get_recent_memories(limit=memory_limit)
        relationships: list[DashboardRelationshipResponse] = []
        for target_agent in runtime.agents:
            target_agent_id = str(target_agent.identity.id)
            if target_agent_id == spatial_agent.agent_id:
                continue
            relationship = build_relationship_snapshot(
                identity_stable_set=list(
                    runtime_agent.profile.fixed.identity_stable_set
                ),
                memories=memories,
                target_agent_id=target_agent_id,
                target_name=target_agent.name,
            )
            relationships.append(
                DashboardRelationshipResponse(
                    target_agent_id=relationship.target_agent_id,
                    target_name=relationship.target_name,
                    affinity_score=relationship.affinity_score,
                    measurement=relationship.measurement,
                    summary=relationship.summary,
                    evidence=[
                        DashboardRelationshipEvidenceResponse(
                            source=evidence.source,
                            content=evidence.content,
                            memory_id=evidence.memory_id,
                            node_type=(
                                evidence.node_type.value
                                if evidence.node_type is not None
                                else None
                            ),
                            importance=evidence.importance,
                            created_at=(
                                evidence.created_at.isoformat()
                                if evidence.created_at is not None
                                else None
                            ),
                        )
                        for evidence in relationship.evidence
                    ],
                )
            )
        agents.append(
            DashboardAgentResponse(
                agent_id=spatial_agent.agent_id,
                name=spatial_agent.name,
                current_action=spatial_agent.current_action,
                destination=spatial_agent.destination,
                tile_position=_map_point_response(spatial_agent.tile_position),
                route_remaining=spatial_agent.route_remaining,
                bubble_kind=spatial_agent.bubble_kind,
                bubble_text=spatial_agent.bubble_text,
                current_plan_context=list(
                    runtime_agent.profile.extended.current_plan_context
                ),
                active_day=_dashboard_plan_item(spatial_agent.active_day),
                active_hourly=_dashboard_plan_item(spatial_agent.active_hourly),
                active_minute=_dashboard_plan_item(spatial_agent.active_minute),
                day_plan=[
                    cast(PlanItemResponse, _dashboard_plan_item(item))
                    for item in spatial_agent.day_plan
                ],
                reflection_status=DashboardReflectionStatusResponse(
                    accumulated_importance=reflection.accumulated_importance,
                    threshold=reflection.config.threshold,
                ),
                relationships=relationships,
                memories=[
                    DashboardMemoryResponse(
                        id=memory.id,
                        node_type=memory.node_type.value,
                        citations=memory.citations,
                        content=memory.content,
                        created_at=memory.created_at.isoformat(),
                        last_accessed_at=memory.last_accessed_at.isoformat(),
                        importance=memory.importance,
                    )
                    for memory in memories
                ],
            )
        )
    state = runtime.state()
    return DashboardStateResponse(
        world=DashboardWorldResponse(
            available=True,
            revision=spatial.revision,
            turn=state.turn,
            current_time=state.current_time.isoformat(),
            scheduler_running=state.scheduler_running,
            cognitive_active=state.cognitive_active,
            effective_time_step_seconds=state.effective_time_step_seconds,
            cognitive_runtime_error=cast(
                str | None, getattr(app.state, "cognitive_runtime_error", None)
            ),
            planning_error=cast(str | None, getattr(runtime, "planning_error", None)),
        ),
        agents=agents,
        events=[
            _dashboard_event_response(event)
            for event in runtime.dashboard_events(limit=event_limit)
        ],
        latest_sequence=runtime.latest_dashboard_sequence,
    )


@app.get("/dashboard/state", response_model=DashboardStateResponse)
async def get_dashboard_state(
    memory_limit: int = 100,
    event_limit: int = 100,
) -> DashboardStateResponse:
    return _dashboard_state_response(
        runtime=_require_runtime(),
        memory_limit=max(1, min(memory_limit, 500)),
        event_limit=max(1, min(event_limit, 500)),
    )


@app.get("/dashboard/events", response_model=list[DashboardEventResponse])
async def get_dashboard_events(
    after: int = 0,
    limit: int = 100,
) -> list[DashboardEventResponse]:
    return [
        _dashboard_event_response(event)
        for event in _require_runtime().dashboard_events(
            after_sequence=max(0, after),
            limit=max(1, min(limit, 500)),
        )
    ]


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
    sender = asyncio.create_task(_send_world_snapshots(websocket, queue))
    receiver = asyncio.create_task(_wait_for_websocket_disconnect(websocket))
    try:
        done, _ = await asyncio.wait(
            {sender, receiver},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            await task
    except WebSocketDisconnect:
        pass
    finally:
        for task in (sender, receiver):
            if not task.done():
                _ = task.cancel()
        _ = await asyncio.gather(sender, receiver, return_exceptions=True)
        stream.unsubscribe(queue)


async def _send_world_snapshots(
    websocket: WebSocket,
    queue: asyncio.Queue[SpatialWorldSnapshot],
) -> None:
    while True:
        snapshot = await queue.get()
        await websocket.send_json(_spatial_response(snapshot).model_dump())


async def _wait_for_websocket_disconnect(websocket: WebSocket) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


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
        cognitive_active=state.cognitive_active,
        effective_time_step_seconds=state.effective_time_step_seconds,
    )


@app.post("/world/step", response_model=WorldStepResponse)
async def post_world_step() -> WorldStepResponse:
    runtime = _require_runtime()
    step_result = await asyncio.to_thread(runtime.step)
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
        cognitive_active=state.cognitive_active,
        effective_time_step_seconds=state.effective_time_step_seconds,
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
