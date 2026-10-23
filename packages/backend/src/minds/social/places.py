"""장소의 한국어 이름 (SPEC §15). 대사·프롬프트·관찰 문장이 모두 이 이름표를 쓴다.

이름표는 `packages/shared/maps/place_names.ko.json`(위치 경로 → 이름) 하나다.
"""

import json
from functools import lru_cache
from pathlib import Path

from world.contracts import LOCATION_SEPARATOR, LocationPath

PLACE_NAMES_PATH = (
    Path(__file__).resolve().parents[4] / "shared" / "maps" / "place_names.ko.json"
)


@lru_cache(maxsize=1)
def place_names() -> dict[LocationPath, str]:
    if not PLACE_NAMES_PATH.exists():
        return {}
    raw = json.loads(PLACE_NAMES_PATH.read_text(encoding="utf-8"))
    return {str(path): str(name) for path, name in dict(raw).items()}


def place_name(location_path: LocationPath) -> str:
    """가장 구체적으로 이름이 있는 경로의 이름. 이름표에 없으면 마지막 구성요소."""
    names = place_names()
    parts = location_path.split(LOCATION_SEPARATOR)
    for depth in range(len(parts), 0, -1):
        name = names.get(LOCATION_SEPARATOR.join(parts[:depth]))
        if name is not None:
            return name
    return parts[-1]
