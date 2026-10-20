from pathlib import Path
from typing import cast

from agents.persona_loader import PersonaLoader
from api.schemas import (
    StatusResponse,
    WorldSchedulerResponse,
    WorldStateResponse,
    WorldStepResponse,
)
from db import init_db
from fastapi import FastAPI, HTTPException
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

app = FastAPI(title="Agent Crossing API")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    persona_dir = Path(__file__).resolve().parents[2] / "persona"
    app.state.persona_loader = PersonaLoader(persona_dir)
    app.state.agent_personas = app.state.persona_loader.load_all()
    persona_names = [persona.agent.id for persona in app.state.agent_personas]
    app.state.world_runtime = None
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


@app.on_event("shutdown")
async def on_shutdown() -> None:
    runtime = cast(WorldRuntime | None, getattr(app.state, "world_runtime", None))
    if runtime is not None:
        await runtime.stop_scheduler()


@app.get("/", response_model=StatusResponse)
async def get_status():
    return {"status": "online", "version": "0.1.0"}


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
        plan_diagnostics=step_result.plan_diagnostics,
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

    uvicorn.run(app, host="0.0.0.0", port=8000)
