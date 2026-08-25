from __future__ import annotations

import asyncio

from .spatial import SpatialWorldRuntime, SpatialWorldSnapshot


class SpatialWorldStream:
    """Advance the spatial runtime once and fan out its latest snapshot."""

    def __init__(
        self,
        *,
        runtime: SpatialWorldRuntime,
        interval_seconds: float = 0.65,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        self.runtime: SpatialWorldRuntime = runtime
        self.interval_seconds: float = interval_seconds
        self._subscribers: set[asyncio.Queue[SpatialWorldSnapshot]] = set()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def start(self) -> bool:
        if self.running:
            return False
        self._task = asyncio.create_task(self._run())
        return True

    async def stop(self) -> bool:
        task = self._task
        self._task = None
        if task is None or task.done():
            return False
        _ = task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    def subscribe(self) -> asyncio.Queue[SpatialWorldSnapshot]:
        queue: asyncio.Queue[SpatialWorldSnapshot] = asyncio.Queue(maxsize=1)
        queue.put_nowait(self.runtime.snapshot())
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SpatialWorldSnapshot]) -> None:
        self._subscribers.discard(queue)

    async def replace_runtime(self, runtime: SpatialWorldRuntime) -> None:
        """Swap worlds while retaining existing WebSocket subscribers."""
        was_running = self.running
        if was_running:
            await self.stop()
        self.runtime = runtime
        self._publish(runtime.snapshot())
        if was_running:
            await self.start()

    async def _run(self) -> None:
        while True:
            snapshot = self.runtime.tick()
            self._publish(snapshot)
            await asyncio.sleep(self.interval_seconds)

    def _publish(self, snapshot: SpatialWorldSnapshot) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                _ = queue.get_nowait()
            queue.put_nowait(snapshot)
