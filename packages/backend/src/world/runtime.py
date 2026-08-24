import asyncio
import datetime
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agents.sim_agent import SimAgent
from llm.governance import (
    ConversationMetrics,
    build_conversation_metrics,
)
from llm.clients.provider_factory import build_provider_client
from agents.world_factory import init_agents

from .engine import SimulationEngine, SimulationEngineConfig, SimulationStepResult
from .session import WorldConversationSession


@dataclass(frozen=True)
class WorldRuntimeConfig:
    agent_persona_names: list[str]
    base_url: str | None
    api_key: str | None
    llm_model: str
    embedding_model: str
    timeout_seconds: float
    persona_dir: str
    dialogue_turn_window: int | None = None
    dialogue_target_turns: int = 5
    language: Literal["ko"] = "ko"
    fallback_on_empty_reply: bool = False
    suppress_repeated_replies: bool = True
    repetition_window: int = 4
    turn_time_step_seconds: int = 45
    tick_interval_seconds: float = 1.0


@dataclass(frozen=True)
class WorldRuntimeState:
    turn: int
    current_time: datetime.datetime
    parse_failures: int
    silent_turns: int
    history_size: int
    scheduler_running: bool
    tick_interval_seconds: float


class WorldRuntime:
    def __init__(
        self,
        *,
        agents: list[SimAgent],
        session: WorldConversationSession,
        engine: SimulationEngine,
        current_time: datetime.datetime,
        tick_interval_seconds: float = 1.0,
    ) -> None:
        if len(agents) != 2:
            raise ValueError("WorldRuntime currently supports exactly two agents")
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be greater than 0")

        self.agents: list[SimAgent] = agents
        self.session: WorldConversationSession = session
        self.engine: SimulationEngine = engine
        self.current_time: datetime.datetime = current_time
        self.tick_interval_seconds: float = tick_interval_seconds
        self.turn: int = 0
        self.parse_failures: int = 0
        self.silent_turns: int = 0
        self._initiator: SimAgent = agents[0]
        self._partner: SimAgent = agents[1]
        self._step_lock: threading.Lock = threading.Lock()
        self._scheduler_task: asyncio.Task[None] | None = None

    def step(self) -> SimulationStepResult:
        with self._step_lock:
            self.turn += 1
            speaker = self.session.next_speaker()
            speaking_partner = (
                self._partner if speaker is self._initiator else self._initiator
            )
            step_result = self.engine.step(
                turn=self.turn,
                current_time=self.current_time,
                speaker=speaker,
                speaking_partner=speaking_partner,
            )
            self.current_time = step_result.now
            if step_result.parse_failure:
                self.parse_failures += 1
            if not step_result.reply:
                self.silent_turns += 1
            return step_result

    def tick(self) -> SimulationStepResult:
        """Advance the single runtime clock by one perceive-plan-act tick."""
        return self.step()

    @property
    def scheduler_running(self) -> bool:
        return self._scheduler_task is not None and not self._scheduler_task.done()

    async def start_scheduler(self) -> bool:
        if self.scheduler_running:
            return False
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        return True

    async def stop_scheduler(self) -> bool:
        if self._scheduler_task is None:
            return False
        task = self._scheduler_task
        self._scheduler_task = None
        if task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def _run_scheduler(self) -> None:
        while True:
            await asyncio.to_thread(self.tick)
            await asyncio.sleep(self.tick_interval_seconds)

    def metrics(self) -> ConversationMetrics:
        return build_conversation_metrics(
            turns=self.turn,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            session_history=self.session.history,
        )

    def state(self) -> WorldRuntimeState:
        return WorldRuntimeState(
            turn=self.turn,
            current_time=self.current_time,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            history_size=len(self.session.history),
            scheduler_running=self.scheduler_running,
            tick_interval_seconds=self.tick_interval_seconds,
        )


def build_world_runtime(*, config: WorldRuntimeConfig) -> WorldRuntime:
    now = datetime.datetime.now()
    llm_client = build_provider_client(
        timeout_seconds=config.timeout_seconds,
        generation_model=config.llm_model,
        embedding_model=config.embedding_model,
        base_url=config.base_url,
        api_key=config.api_key,
    )
    agents = init_agents(
        persona_dir=config.persona_dir,
        agent_persona_names=config.agent_persona_names,
        llm_client=llm_client,
        embedding_model=config.embedding_model,
        now=now,
    )
    session = WorldConversationSession(
        agents=agents,
        dialogue_turn_window=config.dialogue_turn_window,
        dialogue_target_turns=config.dialogue_target_turns,
    )
    engine = SimulationEngine(
        session=session,
        config=SimulationEngineConfig(
            language=config.language,
            turn_time_step_seconds=config.turn_time_step_seconds,
            suppress_repeated_replies=config.suppress_repeated_replies,
            repetition_window=config.repetition_window,
            fallback_on_empty_reply=config.fallback_on_empty_reply,
        ),
    )
    return WorldRuntime(
        agents=agents,
        session=session,
        engine=engine,
        current_time=now,
        tick_interval_seconds=config.tick_interval_seconds,
    )


def default_persona_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "persona")
