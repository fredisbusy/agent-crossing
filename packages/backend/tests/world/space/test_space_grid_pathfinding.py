from world.contracts import TilePosition
from world.space import CollisionGrid, find_path


def make_grid(rows: list[str]) -> CollisionGrid:
    """'#'은 막힘, 나머지는 통행."""
    blocked = tuple(ch == "#" for row in rows for ch in row)
    return CollisionGrid(len(rows[0]), len(rows), blocked)


def tp(x: int, y: int) -> TilePosition:
    return TilePosition(x=x, y=y)


def test_grid_walkable_and_bounds() -> None:
    grid = make_grid(["..#", "..."])
    assert grid.is_walkable(0, 0)
    assert not grid.is_walkable(2, 0)
    assert not grid.is_walkable(-1, 0) and not grid.is_walkable(0, 2)


def test_neighbors_are_four_directional_and_ordered() -> None:
    grid = make_grid(["...", "...", "..."])
    assert list(grid.neighbors(tp(1, 1))) == [tp(1, 0), tp(0, 1), tp(2, 1), tp(1, 2)]
    assert list(grid.neighbors(tp(0, 0))) == [tp(1, 0), tp(0, 1)]


def test_path_straight_excludes_start_includes_goal() -> None:
    grid = make_grid(["....."])
    assert find_path(grid, tp(0, 0), tp(3, 0)) == (tp(1, 0), tp(2, 0), tp(3, 0))


def test_path_detours_around_wall() -> None:
    grid = make_grid(
        [
            "..#..",
            "..#..",
            ".....",
        ]
    )
    path = find_path(grid, tp(0, 0), tp(4, 0))
    assert path is not None
    assert path[-1] == tp(4, 0)
    assert len(path) == 8
    assert all(grid.is_walkable(t.x, t.y) for t in path)


def test_path_none_when_unreachable_or_goal_blocked() -> None:
    grid = make_grid([".#.", ".#.", ".#."])
    assert find_path(grid, tp(0, 0), tp(2, 0)) is None
    assert find_path(grid, tp(0, 0), tp(1, 0)) is None


def test_path_same_point_is_empty() -> None:
    grid = make_grid(["..."])
    assert find_path(grid, tp(1, 0), tp(1, 0)) == ()


def test_path_is_deterministic_with_ties() -> None:
    grid = make_grid(["...", "...", "..."])
    first = find_path(grid, tp(0, 0), tp(2, 2))
    assert first is not None and len(first) == 4
    assert all(find_path(grid, tp(0, 0), tp(2, 2)) == first for _ in range(5))
