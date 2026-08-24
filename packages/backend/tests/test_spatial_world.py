from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.world_map import MapPoint, load_world_map


def _runtime() -> SpatialWorldRuntime:
    return SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(
                agent_id="jiho",
                name="Jiho Park",
                plan_context=("Jiho is visiting Morning Dew Cafe.",),
            ),
            SpatialAgentSeed(
                agent_id="sujin",
                name="Sujin Lee",
                plan_context=("Sujin is working at Morning Dew Cafe.",),
            ),
        ],
    )


def test_spatial_runtime_resolves_plan_alias_and_builds_routes() -> None:
    runtime = _runtime()

    snapshot = runtime.tick()

    assert snapshot.revision == 1
    assert {agent.destination for agent in snapshot.agents} == {
        "Briar Cove > The Honey Cup"
    }
    assert all(
        agent.current_action.startswith("moving_to:") for agent in snapshot.agents
    )
    assert all(agent.route_remaining > 0 for agent in snapshot.agents)


def test_spatial_runtime_advances_only_through_walkable_tiles() -> None:
    runtime = _runtime()
    visited_positions: list[MapPoint] = []
    snapshot = runtime.snapshot()

    for _ in range(20):
        snapshot = runtime.tick()
        visited_positions.extend(agent.tile_position for agent in snapshot.agents)

    assert all(runtime.world_map.is_walkable_tile(point) for point in visited_positions)
    assert any(agent.current_action.startswith("at:") for agent in snapshot.agents)


def test_spatial_runtime_replans_when_agent_plan_changes() -> None:
    runtime = _runtime()
    _ = runtime.tick()
    runtime.set_plan(
        agent_id="jiho", plan="Jiho will study at Riverside Public Library."
    )

    snapshot = runtime.tick()
    jiho = next(agent for agent in snapshot.agents if agent.agent_id == "jiho")

    assert jiho.destination == "Briar Cove > Story House"
    assert jiho.current_action == "moving_to:Story House"


def test_spatial_runtime_keeps_unmapped_plan_idle() -> None:
    runtime = _runtime()
    runtime.set_plan(agent_id="jiho", plan="Jiho thinks quietly about tomorrow.")

    snapshot = runtime.tick()
    jiho = next(agent for agent in snapshot.agents if agent.agent_id == "jiho")

    assert jiho.destination is None
    assert jiho.current_action == "idle:no_mapped_destination"
