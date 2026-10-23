"""마을 시뮬레이션 API (SPEC §15): 백엔드가 단일 권한, 프런트는 스냅샷만 받는다."""

import asyncio
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
from world.contracts import WorldSnapshot
from world.scenarios import build_town, load_scenario
from world.town import TownRuntime

logger = logging.getLogger(__name__)
MAX_ADVANCE_MINUTES = 1440

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
        disconnected = asyncio.create_task(_wait_disconnect(websocket))
        try:
            await _send_snapshot(websocket, runtime.snapshot())
            while True:
                next_snapshot = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait(
                    {next_snapshot, disconnected},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if next_snapshot not in done:
                    next_snapshot.cancel()
                    break
                await _send_snapshot(websocket, next_snapshot.result())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            disconnected.cancel()
            runtime.unsubscribe(queue)

    return app


async def _send_snapshot(websocket: WebSocket, snapshot: WorldSnapshot) -> None:
    await websocket.send_json(
        {"type": "snapshot", "snapshot": snapshot.model_dump(mode="json")}
    )


async def _wait_disconnect(websocket: WebSocket) -> None:
    """클라이언트가 보내는 프레임은 버리고, 끊김만 기다린다."""
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
    except (WebSocketDisconnect, RuntimeError):
        return


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
