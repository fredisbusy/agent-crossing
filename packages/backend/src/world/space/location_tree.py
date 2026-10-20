"""위치 경로 트리 (`Town > Building > Room`). 부모·자식·조상 질의와 부분 트리."""

from world.contracts import LOCATION_SEPARATOR, LocationPath


def split_path(path: LocationPath) -> tuple[str, ...]:
    return tuple(path.split(LOCATION_SEPARATOR))


class LocationTree:
    """경로 문자열 집합으로 만든 트리. 중간 조상은 자동으로 노드가 된다."""

    def __init__(self, paths: tuple[LocationPath, ...] | list[LocationPath]) -> None:
        nodes: set[LocationPath] = set()
        for path in paths:
            parts = split_path(path)
            for depth in range(1, len(parts) + 1):
                nodes.add(LOCATION_SEPARATOR.join(parts[:depth]))
        self._nodes = nodes

    def paths(self) -> tuple[LocationPath, ...]:
        return tuple(sorted(self._nodes))

    def __contains__(self, path: object) -> bool:
        return path in self._nodes

    def parent(self, path: LocationPath) -> LocationPath | None:
        parts = split_path(path)
        if len(parts) <= 1:
            return None
        return LOCATION_SEPARATOR.join(parts[:-1])

    def children(self, path: LocationPath) -> tuple[LocationPath, ...]:
        depth = len(split_path(path)) + 1
        prefix = path + LOCATION_SEPARATOR
        return tuple(
            sorted(n for n in self._nodes if n.startswith(prefix) and len(split_path(n)) == depth)
        )

    def ancestors(self, path: LocationPath) -> tuple[LocationPath, ...]:
        """가까운 부모부터 루트까지."""
        result: list[LocationPath] = []
        current = self.parent(path)
        while current is not None:
            result.append(current)
            current = self.parent(current)
        return tuple(result)

    def depth(self, path: LocationPath) -> int:
        return len(split_path(path))

    def is_within(self, path: LocationPath, ancestor: LocationPath) -> bool:
        """path가 ancestor 자신이거나 그 하위인가."""
        return path == ancestor or path.startswith(ancestor + LOCATION_SEPARATOR)

    def subtree(self, paths: tuple[LocationPath, ...] | list[LocationPath]) -> "LocationTree":
        """주어진 경로(와 그 조상)만 담은 부분 트리. 이 트리에 없는 경로는 무시한다."""
        return LocationTree([p for p in paths if p in self._nodes])
