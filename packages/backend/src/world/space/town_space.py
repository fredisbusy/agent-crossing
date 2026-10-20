"""`contracts.Space` 구현. Tiled 지도 + 충돌 그리드 + 위치 트리."""

from pathlib import Path

from world.contracts import LocationPath, TilePosition

from .grid import CollisionGrid
from .location_tree import LocationTree, split_path
from .pathfinding import find_path as astar
from .tiled_loader import TiledMap, TileRect, load_tiled_map

TOWN_NAME = "Smallville"
DEFAULT_MAP_PATH = Path(__file__).resolve().parents[4] / "shared" / "maps" / "town.json"


class TownSpace:
    def __init__(self, tiled: TiledMap) -> None:
        self._grid = CollisionGrid.from_map(tiled)
        self._rects: dict[LocationPath, TileRect] = {
            r.location_path: r.rect for r in tiled.regions
        }
        self._rects.setdefault(
            TOWN_NAME, TileRect(x=0, y=0, width=tiled.width, height=tiled.height)
        )
        self._tree = LocationTree(list(self._rects))
        # 깊은 경로, 작은 면적, 이름 순으로 정렬해 location_at이 첫 일치를 바로 돌려주게 한다.
        self._by_specificity = sorted(
            self._rects.items(),
            key=lambda item: (-len(split_path(item[0])), item[1].area, item[0]),
        )

    @property
    def grid(self) -> CollisionGrid:
        return self._grid

    @property
    def tree(self) -> LocationTree:
        return self._tree

    def tile_of(self, location_path: LocationPath) -> TilePosition | None:
        rect = self._rects.get(location_path)
        if rect is None:
            return None
        return self._nearest_walkable(rect)

    def location_at(self, tile: TilePosition) -> LocationPath:
        for path, rect in self._by_specificity:
            if rect.contains(tile.x, tile.y):
                return path
        return TOWN_NAME

    def find_path(
        self, start: TilePosition, goal: TilePosition
    ) -> tuple[TilePosition, ...] | None:
        return astar(self._grid, start, goal)

    def location_paths(self) -> tuple[LocationPath, ...]:
        return tuple(sorted(self._rects))

    def _nearest_walkable(self, rect: TileRect) -> TilePosition | None:
        # 중심은 2배 좌표로 두어 정수 연산만 쓴다. 동점은 (y, x) 작은 쪽.
        cx2, cy2 = 2 * rect.x + rect.width - 1, 2 * rect.y + rect.height - 1
        best: tuple[int, int, int] | None = None
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                if not self._grid.is_walkable(x, y):
                    continue
                dist = (2 * x - cx2) ** 2 + (2 * y - cy2) ** 2
                if best is None or (dist, y, x) < best:
                    best = (dist, y, x)
        return None if best is None else TilePosition(x=best[2], y=best[1])


def load_town_space(path: Path | None = None) -> TownSpace:
    return TownSpace(load_tiled_map(path or DEFAULT_MAP_PATH))
