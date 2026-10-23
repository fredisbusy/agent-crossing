"""TownRuntime: 락 직렬화, 최신만 보관하는 구독 큐, 스케줄러."""

import asyncio

from town_fakes import CAFE, ScriptedMind, make_sim
from world.town import TownRuntime


def make_runtime(interval: float = 0.0) -> TownRuntime:
    sim = make_sim({"ann": (CAFE, ScriptedMind())})
    return TownRuntime(sim, tick_interval_seconds=interval)


def test_advance_ticks_and_returns_latest_snapshot() -> None:
    async def scenario() -> None:
        runtime = make_runtime()
        snapshot = await runtime.advance(3)
        assert snapshot.tick == 3
        assert runtime.snapshot().tick == 3

    asyncio.run(scenario())


def test_subscriber_queue_keeps_only_latest_snapshot() -> None:
    async def scenario() -> None:
        runtime = make_runtime()
        queue = runtime.subscribe()
        await runtime.advance(5)
        assert queue.qsize() == 1
        assert queue.get_nowait().tick == 5
        runtime.unsubscribe(queue)
        await runtime.advance(1)
        assert queue.empty()

    asyncio.run(scenario())


def test_concurrent_advances_are_serialized() -> None:
    async def scenario() -> None:
        runtime = make_runtime()
        queue = runtime.subscribe()
        seen: list[int] = []

        async def collect() -> None:
            while True:
                seen.append((await queue.get()).tick)

        collector = asyncio.create_task(collect())
        await asyncio.gather(runtime.advance(4), runtime.advance(4))
        await asyncio.sleep(0)
        collector.cancel()
        assert runtime.snapshot().tick == 8
        assert seen == sorted(seen) and seen[-1] == 8

    asyncio.run(scenario())


def test_scheduler_start_stop() -> None:
    async def scenario() -> None:
        runtime = make_runtime(interval=0.001)
        assert not runtime.scheduler_running
        await runtime.start()
        await runtime.start()
        assert runtime.scheduler_running
        await asyncio.sleep(0.05)
        await runtime.stop()
        assert not runtime.scheduler_running
        ticks = runtime.snapshot().tick
        assert ticks > 0
        await asyncio.sleep(0.02)
        assert runtime.snapshot().tick == ticks

    asyncio.run(scenario())
