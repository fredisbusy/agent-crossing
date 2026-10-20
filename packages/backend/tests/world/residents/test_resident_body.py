import datetime

import pytest
from world.contracts import ActionIntent, ResidentPublicView, TilePosition
from world.residents import Body

NOW = datetime.datetime(2025, 2, 13, 8, 0)
ROOM_A = "Smallville > Hobbs Cafe > Seating"
ROOM_B = "Smallville > Town Square"
ROOM_C = "Smallville > Oak Hill College > Library"


class LineSpace:
    """1x10 일렬 공간. 0~1 카페, 5~9 광장, 도서관은 경로가 없다."""

    def tile_of(self, location_path: str) -> TilePosition | None:
        return {
            ROOM_A: TilePosition(x=0, y=0),
            ROOM_B: TilePosition(x=7, y=0),
            ROOM_C: TilePosition(x=3, y=5),
        }.get(location_path)

    def location_at(self, tile: TilePosition) -> str:
        if tile.x <= 1:
            return ROOM_A
        return ROOM_B if tile.x >= 5 else "Smallville"

    def find_path(
        self, start: TilePosition, goal: TilePosition
    ) -> tuple[TilePosition, ...] | None:
        if goal.y != 0:
            return None
        step = 1 if goal.x > start.x else -1
        return tuple(TilePosition(x=x, y=0) for x in range(start.x + step, goal.x + step, step))

    def location_paths(self) -> tuple[str, ...]:
        return (ROOM_A, ROOM_B, ROOM_C)


def make_body() -> Body:
    return Body(
        resident_id="ann", display_name="Ann", space=LineSpace(), start_location=ROOM_A
    )


def intent(where: str, minutes: int = 30) -> ActionIntent:
    return ActionIntent(
        kind="move",
        description="걸어간다",
        location_path=where,
        until=NOW + datetime.timedelta(minutes=minutes),
    )


def test_new_body_has_no_action_and_counts_as_expired() -> None:
    body = make_body()
    assert body.state.action is None
    assert body.is_expired(NOW)


def test_moves_one_tile_per_step_and_updates_location_on_arrival() -> None:
    body = make_body()
    assert body.set_intent(intent(ROOM_B), NOW) is None
    assert body.is_moving
    body.step()
    assert body.state.tile == TilePosition(x=1, y=0)
    assert body.state.location_path == ROOM_A
    for _ in range(6):
        body.step()
    assert body.state.tile == TilePosition(x=7, y=0)
    assert body.state.location_path == ROOM_B
    assert not body.is_moving


def test_move_counts_as_expired_on_arrival() -> None:
    body = make_body()
    body.set_intent(intent(ROOM_B), NOW)
    assert not body.is_expired(NOW)
    for _ in range(7):
        body.step()
    assert body.is_expired(NOW)


def test_action_expires_at_until() -> None:
    body = make_body()
    body.set_intent(intent(ROOM_A, minutes=5).model_copy(update={"kind": "idle"}), NOW)
    assert not body.is_expired(NOW + datetime.timedelta(minutes=4))
    assert body.is_expired(NOW + datetime.timedelta(minutes=5))


def test_unreachable_destination_becomes_idle_with_observation() -> None:
    body = make_body()
    observation = body.set_intent(intent(ROOM_C), NOW)
    assert observation is not None
    assert "갈 수 없었다" in observation.text
    assert body.state.action is not None
    assert body.state.action.kind == "idle"
    assert body.state.location_path == ROOM_A
    assert not body.is_moving


def test_unknown_destination_is_also_unreachable() -> None:
    body = make_body()
    assert body.set_intent(intent("Smallville > Nowhere"), NOW) is not None


def test_body_does_not_move_during_conversation() -> None:
    body = make_body()
    body.set_intent(intent(ROOM_B), NOW)
    body.conversation_id = "conv-1"
    body.step()
    assert body.state.tile == TilePosition(x=0, y=0)
    body.conversation_id = None
    body.step()
    assert body.state.tile == TilePosition(x=1, y=0)


def test_missing_start_location_raises() -> None:
    with pytest.raises(ValueError):
        Body(resident_id="x", display_name="X", space=LineSpace(), start_location="Nope")


def test_public_view_has_no_mind_kind() -> None:
    assert "mind_kind" not in ResidentPublicView.model_fields
    assert "mind" not in ResidentPublicView.model_fields


def test_repeated_failure_to_same_destination_is_reported_once() -> None:
    body = make_body()
    assert body.set_intent(intent(ROOM_C), NOW) is not None
    assert body.set_intent(intent(ROOM_C), NOW) is None
    assert body.state.action is not None and body.state.action.kind == "idle"
    assert body.set_intent(intent(ROOM_B), NOW) is None
    assert body.set_intent(intent(ROOM_C), NOW) is not None
