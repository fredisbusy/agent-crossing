import datetime

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
        "브라이어 코브 > 허니컵 카페"
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

    assert jiho.destination == "브라이어 코브 > 스토리하우스 도서관"
    assert jiho.current_action == "moving_to:스토리하우스 도서관"


def test_home_arrival_requires_a_separate_inside_transition() -> None:
    runtime = _runtime()
    runtime.set_plan(agent_id="jiho", plan="지호의 집에서 조용히 쉰다.")

    jiho = next(
        agent for agent in runtime.snapshot().agents if agent.agent_id == "jiho"
    )
    for _ in range(80):
        snapshot = runtime.tick()
        jiho = next(agent for agent in snapshot.agents if agent.agent_id == "jiho")
        if jiho.current_action.startswith("arrived_at_door:"):
            break

    assert jiho.destination == "브라이어 코브 > 지호의 집"
    assert jiho.tile_position == MapPoint(5, 15)
    assert jiho.current_action == "arrived_at_door:지호의 집"

    snapshot = runtime.tick()
    jiho = next(agent for agent in snapshot.agents if agent.agent_id == "jiho")

    assert jiho.tile_position == MapPoint(5, 15)
    assert jiho.current_action == "inside:지호의 집"


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


def test_planning_error_is_diagnostics_only_and_does_not_freeze_movement() -> None:
    """A plan-generation failure (for any agent) must not stop the village.

    `planning_error` is surfaced for the dashboard/UI, but movement is
    deterministic and independent from LLM latency/failures: agents keep
    following their last-known plan/route/destination while a failure is
    being retried in the background.
    """
    runtime = _runtime()

    runtime.set_planning_error("Jiho Park: minute plan parse failed")
    snapshot = runtime.tick()

    assert snapshot.planning_error == "Jiho Park: minute plan parse failed"
    assert {agent.destination for agent in snapshot.agents} == {
        "브라이어 코브 > 허니컵 카페"
    }
    assert all(
        agent.current_action.startswith("moving_to:") for agent in snapshot.agents
    )
    assert all(agent.route_remaining > 0 for agent in snapshot.agents)

    runtime.set_planning_error(None)
    cleared_snapshot = runtime.tick()
    assert cleared_snapshot.planning_error is None


def test_position_history_is_recorded_only_on_change_once_clock_is_known() -> None:
    runtime = _runtime()
    now = datetime.datetime(2026, 8, 25, 8, 0)

    # No game-clock time set yet: ticking must not grow the history log.
    _ = runtime.tick()
    assert runtime.export_position_history() == []

    for offset in range(5):
        runtime.update_world_state(
            current_time=now + datetime.timedelta(minutes=offset),
            turn=offset,
            scheduler_running=False,
        )
        _ = runtime.tick()

    history = runtime.export_position_history()
    assert history
    jiho_entries = [entry for entry in history if entry.agent_id == "jiho"]
    assert jiho_entries
    # Every recorded entry is a genuine tile/destination/action change.
    for previous, current in zip(jiho_entries, jiho_entries[1:]):
        assert (
            previous.tile_position != current.tile_position
            or previous.destination_path != current.destination_path
            or previous.current_action != current.current_action
        )
    assert all(entry.occurred_at is not None for entry in history)


def test_position_history_round_trips_through_restore() -> None:
    runtime = _runtime()
    now = datetime.datetime(2026, 8, 25, 8, 0)
    for offset in range(3):
        runtime.update_world_state(
            current_time=now + datetime.timedelta(minutes=offset),
            turn=offset,
            scheduler_running=False,
        )
        _ = runtime.tick()
    exported = runtime.export_position_history()
    assert exported

    other = _runtime()
    other.restore_position_history(exported)

    assert other.export_position_history() == exported
