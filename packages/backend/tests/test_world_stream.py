import asyncio
from dataclasses import dataclass, field
from typing import cast

from fastapi import WebSocket, WebSocketDisconnect

from api.main import app, world_websocket
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.stream import SpatialWorldStream
from world.world_map import load_world_map


def _runtime() -> SpatialWorldRuntime:
    return SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(
                agent_id="jiho",
                name="Jiho Park",
                plan_context=("Jiho is visiting Morning Dew Cafe.",),
            )
        ],
    )


def test_world_stream_broadcasts_monotonic_snapshots() -> None:
    asyncio.run(_assert_world_stream_broadcasts_monotonic_snapshots())


async def _assert_world_stream_broadcasts_monotonic_snapshots() -> None:
    stream = SpatialWorldStream(runtime=_runtime(), interval_seconds=0.01)
    queue = stream.subscribe()

    started = await stream.start()
    initial = await asyncio.wait_for(queue.get(), timeout=0.2)
    updated = await asyncio.wait_for(queue.get(), timeout=0.2)
    stopped = await stream.stop()

    assert started is True
    assert stopped is True
    assert initial.revision == 0
    assert updated.revision > initial.revision


@dataclass
class _DisconnectingWebSocket:
    accepted: bool = False
    payloads: list[dict[str, object]] = field(default_factory=list)

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: object) -> None:
        self.payloads.append(cast(dict[str, object], data))
        raise WebSocketDisconnect()


def test_world_websocket_sends_initial_snapshot_and_unsubscribes() -> None:
    asyncio.run(_assert_world_websocket_sends_initial_snapshot_and_unsubscribes())


async def _assert_world_websocket_sends_initial_snapshot_and_unsubscribes() -> None:
    stream = SpatialWorldStream(runtime=_runtime())
    app.state.spatial_stream = stream
    websocket = _DisconnectingWebSocket()

    await world_websocket(cast(WebSocket, cast(object, websocket)))

    assert websocket.accepted is True
    assert websocket.payloads[0]["map_id"] == "briar-cove"
    assert websocket.payloads[0]["revision"] == 0
    assert stream.subscriber_count == 0
