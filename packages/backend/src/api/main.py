"""마을 시뮬레이션 API (SPEC §15): 백엔드가 단일 권한, 프런트는 스냅샷만 받는다."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from api.schemas import StatusResponse, WorldSchedulerResponse, WorldStateResponse
from db import init_db
from fastapi import FastAPI, Query, Request, Response, WebSocket
from fastapi.websockets import WebSocketDisconnect
from settings import (
    TOWN_AGENT_COUNT,
    TOWN_AGENTS,
    TOWN_SCENARIO,
    TOWN_SEED,
    WORLD_TICK_INTERVAL_SECONDS,
)
from world.contracts import WorldDelta, WorldSnapshot
from world.scenarios import build_town, load_scenario
from world.town import TownRuntime, diff_snapshots

logger = logging.getLogger(__name__)
MAX_ADVANCE_MINUTES = 1440
RESYNC_REQUEST = "resync"
"""프런트가 보내는 다시 맞춤 요청의 `type` (shared `WorldClientMessage`)."""

RuntimeFactory = Callable[[], Awaitable[TownRuntime]]


async def build_default_runtime() -> TownRuntime:
    """환경 설정(TOWN_*)으로 마을을 조립한다. 무거운 조립은 스레드에서 한다."""
    agent_ids = [i.strip() for i in TOWN_AGENTS.split(",") if i.strip()] or None

    def _build() -> TownRuntime:
        town = build_town(
            load_scenario(TOWN_SCENARIO),
            agent_ids=agent_ids,
            agent_count=TOWN_AGENT_COUNT,
            seed=TOWN_SEED,
        )
        return TownRuntime(
            town.simulation, tick_interval_seconds=WORLD_TICK_INTERVAL_SECONDS
        )

    return await asyncio.to_thread(_build)


def create_app(
    *,
    runtime_factory: RuntimeFactory = build_default_runtime,
    init_database: Callable[[], None] = init_db,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await asyncio.to_thread(init_database)
        except Exception:
            logger.warning("DB 초기화 실패 - 마을은 DB를 쓰지 않으므로 계속 기동한다", exc_info=True)
        runtime = await runtime_factory()
        app.state.town_runtime = runtime
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="Agent Crossing API", lifespan=lifespan)

    def runtime_of(source: Request | WebSocket) -> TownRuntime:
        return cast(TownRuntime, source.app.state.town_runtime)

    def scheduler_response(runtime: TownRuntime) -> WorldSchedulerResponse:
        return WorldSchedulerResponse(
            running=runtime.scheduler_running,
            tick=runtime.snapshot().tick,
            tick_interval_seconds=runtime.tick_interval_seconds,
        )

    @app.get("/", response_model=StatusResponse)
    async def get_status() -> StatusResponse:
        return StatusResponse(status="online", version="0.1.0")

    @app.get("/world/state", response_model=WorldStateResponse)
    async def get_world_state(request: Request) -> WorldStateResponse:
        runtime = runtime_of(request)
        return WorldStateResponse(
            snapshot=runtime.snapshot(),
            scheduler_running=runtime.scheduler_running,
            tick_interval_seconds=runtime.tick_interval_seconds,
            last_error=runtime.last_error,
        )

    @app.get("/world/text")
    async def get_world_text(request: Request) -> Response:
        """QA 훅 (SPEC §15): `TownSimulation.text_state()` JSON 그대로."""
        return Response(
            content=runtime_of(request).text_state(), media_type="application/json"
        )

    @app.post("/world/advance", response_model=WorldSnapshot)
    async def post_world_advance(
        request: Request,
        minutes: int = Query(ge=1, le=MAX_ADVANCE_MINUTES),
    ) -> WorldSnapshot:
        return await runtime_of(request).advance(minutes)

    @app.post("/world/tick/start", response_model=WorldSchedulerResponse)
    async def post_world_tick_start(request: Request) -> WorldSchedulerResponse:
        runtime = runtime_of(request)
        await runtime.start()
        return scheduler_response(runtime)

    @app.post("/world/tick/stop", response_model=WorldSchedulerResponse)
    async def post_world_tick_stop(request: Request) -> WorldSchedulerResponse:
        runtime = runtime_of(request)
        await runtime.stop()
        return scheduler_response(runtime)

    @app.websocket("/ws/world")
    async def ws_world(websocket: WebSocket) -> None:
        runtime = runtime_of(websocket)
        await websocket.accept()
        queue = runtime.subscribe()
        resync = asyncio.Event()
        disconnected = asyncio.create_task(_receive_requests(websocket, resync))
        try:
            await _stream_world(websocket, runtime, queue, resync, disconnected)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            disconnected.cancel()
            runtime.unsubscribe(queue)

    return app


async def _stream_world(
    websocket: WebSocket,
    runtime: TownRuntime,
    queue: asyncio.Queue[WorldSnapshot],
    resync: asyncio.Event,
    disconnected: asyncio.Task[None],
) -> None:
    """처음과 다시 맞춤 요청마다 전체 스냅샷, 그 사이에는 마지막으로 보낸 상태와의 delta (SPEC §9)."""
    last_sent = runtime.snapshot()
    await _send_snapshot(websocket, last_sent)
    next_snapshot: asyncio.Future[WorldSnapshot] | None = None
    while True:
        if next_snapshot is None:
            next_snapshot = asyncio.ensure_future(queue.get())
        resync_wait = asyncio.ensure_future(resync.wait())
        done, _ = await asyncio.wait(
            {next_snapshot, resync_wait, disconnected},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if disconnected in done:
            next_snapshot.cancel()
            resync_wait.cancel()
            return
        if resync_wait in done:
            resync.clear()
            last_sent = runtime.snapshot()
            await _send_snapshot(websocket, last_sent)
        else:
            resync_wait.cancel()
        if next_snapshot in done:
            latest = next_snapshot.result()
            next_snapshot = None
            if latest.tick > last_sent.tick:
                await _send_delta(websocket, diff_snapshots(last_sent, latest))
                last_sent = latest


async def _send_snapshot(websocket: WebSocket, snapshot: WorldSnapshot) -> None:
    await websocket.send_json(
        {"type": "snapshot", "snapshot": snapshot.model_dump(mode="json")}
    )


async def _send_delta(websocket: WebSocket, delta: WorldDelta) -> None:
    payload = delta.model_dump(mode="json")
    await websocket.send_json({"type": "delta", **payload})


async def _receive_requests(websocket: WebSocket, resync: asyncio.Event) -> None:
    """클라이언트 프레임 중 다시 맞춤 요청만 받고 나머지는 버린다. 끊기면 끝난다."""
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if _is_resync_request(message.get("text")):
                resync.set()
    except (WebSocketDisconnect, RuntimeError):
        return


def _is_resync_request(text: object) -> bool:
    """`{"type": "resync"}`: 프런트가 delta를 합치지 못해 전체 스냅샷을 다시 원한다."""
    if not isinstance(text, str):
        return False
    try:
        parsed = cast(object, json.loads(text))
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and cast(dict[str, object], parsed).get("type") == RESYNC_REQUEST


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
