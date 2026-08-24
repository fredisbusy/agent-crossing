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

    for _ in range(40):
        snapshot = runtime.tick()
        visited_positions.extend(agent.tile_position for agent in snapshot.agents)
        assert len({agent.tile_position for agent in snapshot.agents}) == len(
            snapshot.agents
        )

    assert all(runtime.world_map.is_walkable_tile(point) for point in visited_positions)
    assert all(agent.current_action.startswith("at:") for agent in snapshot.agents)
    assert {agent.tile_position for agent in snapshot.agents} == {
        MapPoint(8, 8),
        MapPoint(8, 9),
    }


def test_spatial_runtime_never_moves_diagonally() -> None:
    runtime = _runtime()
    previous_positions = {
        agent.agent_id: agent.tile_position for agent in runtime.snapshot().agents
    }

    for _ in range(20):
        snapshot = runtime.tick()
        for agent in snapshot.agents:
            previous = previous_positions[agent.agent_id]
            distance = abs(agent.tile_position.x - previous.x) + abs(
                agent.tile_position.y - previous.y
            )
            assert distance in {0, 1}
            previous_positions[agent.agent_id] = agent.tile_position


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


def test_spatial_runtime_exposes_speech_and_restores_action_overlay() -> None:
    runtime = _runtime()
    initial_jiho = next(
        agent for agent in runtime.snapshot().agents if agent.agent_id == "jiho"
    )
    assert initial_jiho.bubble_kind == "action"
    assert initial_jiho.bubble_text == initial_jiho.plan

    runtime.set_cognitive_overlay(
        agent_id="jiho",
        kind="speech",
        text="수진아, 좋은 아침이야.",
    )
    speaking_jiho = next(
        agent for agent in runtime.snapshot().agents if agent.agent_id == "jiho"
    )
    assert speaking_jiho.bubble_kind == "speech"
    assert speaking_jiho.bubble_text == "수진아, 좋은 아침이야."

    runtime.clear_cognitive_overlays()
    active_jiho = next(
        agent for agent in runtime.snapshot().agents if agent.agent_id == "jiho"
    )
    assert active_jiho.bubble_kind == "action"
    assert active_jiho.bubble_text == active_jiho.plan


def test_spatial_runtime_does_not_publish_blank_thought_overlay() -> None:
    runtime = _runtime()

    runtime.set_cognitive_overlay(agent_id="jiho", kind="thought", text="   ")

    jiho = next(
        agent for agent in runtime.snapshot().agents if agent.agent_id == "jiho"
    )
    assert jiho.bubble_kind == "action"


def test_planning_error_clears_non_authoritative_plan_and_stops_movement() -> None:
    runtime = _runtime()

    runtime.set_planning_error("Jiho Park: minute plan parse failed")
    snapshot = runtime.tick()

    assert snapshot.planning_error == "Jiho Park: minute plan parse failed"
    assert all(agent.active_minute is None for agent in snapshot.agents)
    assert all(agent.destination is None for agent in snapshot.agents)
    assert all(agent.current_action == "planning_error" for agent in snapshot.agents)
    assert all(agent.plan == "" for agent in snapshot.agents)
