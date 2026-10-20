"""충돌 그리드. 통행 가능 여부와 4방향 이웃만 안다."""

from collections.abc import Iterator

from world.contracts import TilePosition

from .tiled_loader import TiledMap

# 4방향 이웃 순서(위, 왼, 오른, 아래). A* 동점 처리의 결정론 근거.
NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = ((0, -1), (-1, 0), (1, 0), (0, 1))


class CollisionGrid:
    """행 우선 1차원 `blocked`에서 True면 막힌 타일."""

    def __init__(self, width: int, height: int, blocked: tuple[bool, ...]) -> None:
        if len(blocked) != width * height:
            raise ValueError("blocked 길이가 width*height와 다릅니다.")
        self.width = width
        self.height = height
        self._blocked = blocked

    @classmethod
    def from_map(cls, tiled: TiledMap) -> "CollisionGrid":
        return cls(tiled.width, tiled.height, tuple(v != 0 for v in tiled.collision))

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and not self._blocked[y * self.width + x]

    def neighbors(self, tile: TilePosition) -> Iterator[TilePosition]:
        for dx, dy in NEIGHBOR_OFFSETS:
            nx, ny = tile.x + dx, tile.y + dy
            if self.is_walkable(nx, ny):
                yield TilePosition(x=nx, y=ny)
