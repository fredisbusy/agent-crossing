"""마을 런타임: 시뮬레이션 하나를 비동기로 진행하고 스냅샷을 구독자에게 알린다 (SPEC §15).

FastAPI에 의존하지 않는다. 진행은 락 하나로 직렬화하고, 구독자별 크기 1 큐에는
최신 스냅샷만 남겨 느린 클라이언트가 틱을 막지 못하게 한다.
"""

import asyncio
import contextlib
import logging

from world.contracts import WorldSnapshot

from .simulation import TownSimulation

logger = logging.getLogger(__name__)


class TownRuntime:
    def __init__(
        self, simulation: TownSimulation, *, tick_interval_seconds: float
    ) -> None:
        self._simulation = simulation
        self.tick_interval_seconds = tick_interval_seconds
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[WorldSnapshot]] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._snapshot = simulation.snapshot()
        self._text = simulation.text_state()
        """마지막으로 완결된 틱의 상태. 틱 도중의 반쪽 상태는 밖으로 내지 않는다."""
        self.last_error: str | None = None

    @property
    def scheduler_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def snapshot(self) -> WorldSnapshot:
        return self._snapshot

    def text_state(self) -> str:
        return self._text

    async def advance(self, minutes: int) -> WorldSnapshot:
        """`minutes`틱을 차례로 돌리고 매 틱 뒤 구독자에게 알린다."""
        async with self._lock:
            for _ in range(minutes):
                await self._simulation.tick()
                self._snapshot = self._simulation.snapshot()
                self._text = self._simulation.text_state()
                self._publish(self._snapshot)
            return self._snapshot

    def subscribe(self) -> asyncio.Queue[WorldSnapshot]:
        queue: asyncio.Queue[WorldSnapshot] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[WorldSnapshot]) -> None:
        self._subscribers.discard(queue)

    def _publish(self, snapshot: WorldSnapshot) -> None:
        for queue in self._subscribers:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(snapshot)

    async def start(self) -> None:
        if self.scheduler_running:
            return
        self._stop_event = asyncio.Event()
        self.last_error = None
        self._task = asyncio.create_task(self._run(self._stop_event))

    async def stop(self) -> None:
        """진행 중인 틱은 끝까지 마친 뒤 멈춘다. 취소는 틱 사이 sleep에만 걸린다."""
        task = self._task
        self._stop_event.set()
        if task is not None:
            await task
        self._task = None

    async def _run(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await self.advance(1)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=self.tick_interval_seconds
                    )
        except Exception as error:
            self.last_error = f"{type(error).__name__}: {error}"
            logger.exception("마을 스케줄러가 오류로 멈췄다")
