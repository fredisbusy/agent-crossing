"""TownRuntime: 락 직렬화, 최신만 보관하는 구독 큐, 스케줄러."""

import asyncio
import json

from town_fakes import CAFE, ScriptedMind, make_sim
from world.contracts import ActionIntent, MindContext
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


class SlowMind(ScriptedMind):
    """next_action에서 양보하며 동시 진입 수와 완료 수를 센다."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.inside = 0
        self.max_inside = 0
        self.finished = 0

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        self.inside += 1
        self.max_inside = max(self.max_inside, self.inside)
        self.entered.set()
        await asyncio.sleep(0.05)
        self.inside -= 1
        self.finished += 1
        return await super().next_action(ctx)


def test_concurrent_advances_are_serialized() -> None:
    async def scenario() -> None:
        mind = SlowMind()
        runtime = TownRuntime(
            make_sim({"ann": (CAFE, mind)}), tick_interval_seconds=0.0
        )
        await asyncio.gather(runtime.advance(2), runtime.advance(2))
        assert runtime.snapshot().tick == 4
        assert mind.max_inside == 1

    asyncio.run(scenario())


def test_stop_during_tick_completes_that_tick() -> None:
    async def scenario() -> None:
        mind = SlowMind()
        runtime = TownRuntime(
            make_sim({"ann": (CAFE, mind)}), tick_interval_seconds=0.01
        )
        queue = runtime.subscribe()
        await runtime.start()
        await mind.entered.wait()
        assert mind.finished == 0
        await runtime.stop()
        assert mind.finished == 1 and mind.inside == 0
        assert runtime.snapshot().tick == 1
        assert queue.qsize() == 1 and queue.get_nowait().tick == 1
        await asyncio.sleep(0.1)
        assert runtime.snapshot().tick == 1 and queue.empty()
        assert not runtime.scheduler_running

    asyncio.run(scenario())


def test_snapshot_is_last_completed_tick_during_tick() -> None:
    async def scenario() -> None:
        mind = SlowMind()
        runtime = TownRuntime(make_sim({"ann": (CAFE, mind)}), tick_interval_seconds=0.0)
        task = asyncio.create_task(runtime.advance(1))
        await mind.entered.wait()
        assert runtime.snapshot().tick == 0
        assert json.loads(runtime.text_state())["tick"] == 0
        await task
        assert json.loads(runtime.text_state())["tick"] == 1

    asyncio.run(scenario())


def test_scheduler_error_is_recorded() -> None:
    async def scenario() -> None:
        class Boom(ScriptedMind):
            async def next_action(self, ctx: MindContext) -> ActionIntent:
                raise ValueError("boom")

        runtime = TownRuntime(make_sim({"ann": (CAFE, Boom())}), tick_interval_seconds=0.0)
        await runtime.start()
        await asyncio.sleep(0.05)
        assert not runtime.scheduler_running
        assert runtime.last_error == "ValueError: boom"

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
