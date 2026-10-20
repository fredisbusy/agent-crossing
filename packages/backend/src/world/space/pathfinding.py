"""4방향 A*. 같은 입력이면 항상 같은 경로를 낸다."""

import heapq

from world.contracts import TilePosition

from .grid import CollisionGrid

Coord = tuple[int, int]


def _manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def find_path(
    grid: CollisionGrid, start: TilePosition, goal: TilePosition
) -> tuple[TilePosition, ...] | None:
    """start 제외, goal 포함. 막힌 goal이거나 경로가 없으면 None, 같은 지점이면 빈 튜플."""
    if not grid.is_walkable(goal.x, goal.y):
        return None
    if start == goal:
        return ()
    if not grid.is_walkable(start.x, start.y):
        return None
    s, g = (start.x, start.y), (goal.x, goal.y)
    # 우선순위 (f, h, y, x): 동점이면 목표에 가깝고 좌표가 작은 쪽 먼저.
    open_heap: list[tuple[int, int, int, int]] = [(_manhattan(s, g), _manhattan(s, g), s[1], s[0])]
    cost: dict[Coord, int] = {s: 0}
    parent: dict[Coord, Coord] = {}
    closed: set[Coord] = set()
    while open_heap:
        _, _, cy, cx = heapq.heappop(open_heap)
        current = (cx, cy)
        if current in closed:
            continue
        if current == g:
            return _rebuild(parent, s, g)
        closed.add(current)
        for nxt in grid.neighbors(TilePosition(x=cx, y=cy)):
            n = (nxt.x, nxt.y)
            new_cost = cost[current] + 1
            if n in closed or new_cost >= cost.get(n, new_cost + 1):
                continue
            cost[n] = new_cost
            parent[n] = current
            h = _manhattan(n, g)
            heapq.heappush(open_heap, (new_cost + h, h, n[1], n[0]))
    return None


def _rebuild(parent: dict[Coord, Coord], start: Coord, goal: Coord) -> tuple[TilePosition, ...]:
    steps: list[TilePosition] = []
    node = goal
    while node != start:
        steps.append(TilePosition(x=node[0], y=node[1]))
        node = parent[node]
    steps.reverse()
    return tuple(steps)
