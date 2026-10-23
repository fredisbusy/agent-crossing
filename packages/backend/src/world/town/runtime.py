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

    @property
    def scheduler_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def snapshot(self) -> WorldSnapshot:
        return self._simulation.snapshot()

    def text_state(self) -> str:
        return self._simulation.text_state()

    async def advance(self, minutes: int) -> WorldSnapshot:
        """`minutes`틱을 차례로 돌리고 매 틱 뒤 구독자에게 알린다."""
        async with self._lock:
            for _ in range(minutes):
                await self._simulation.tick()
                self._publish(self._simulation.snapshot())
            return self._simulation.snapshot()

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
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        try:
            while True:
                await self.advance(1)
                await asyncio.sleep(self.tick_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("마을 스케줄러가 오류로 멈췄다")
