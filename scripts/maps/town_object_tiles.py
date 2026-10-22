"""Tiled에서 가구·장식을 그림으로 보이게 하는 '그림 모음' 타일셋 (SPEC §15).

가구·장식 객체는 이 타일셋의 타일 객체(gid)로 둔다. Tiled 규칙상 타일 객체의 y는 **아랫변**이다
(사각형 객체는 윗변). 게임·검증기는 gid가 있으면 y에서 높이를 빼 윗변으로 읽는다.
그림 파일은 `export_tileset.py`가 `packages/shared/maps/objects/<프레임>.png`로 만든다.
"""

from typing import Any

from town_decor import DECOR_FRAMES
from town_furniture import FRAME_CELLS

TILE = 16
NAME = "town-objects"
FIRSTGID = 9
"""의미 타일 8종(gid 1..8) 다음 번호."""
IMAGE_DIR = "objects"

# 프레임 이름 -> (너비, 높이) 칸. 순서가 타일 id다(이름순, 고정).
OBJECT_CELLS: dict[str, tuple[int, int]] = dict(sorted({**FRAME_CELLS, **DECOR_FRAMES}.items()))
OBJECT_FRAMES: tuple[str, ...] = tuple(OBJECT_CELLS)
GID_OF: dict[str, int] = {frame: FIRSTGID + i for i, frame in enumerate(OBJECT_FRAMES)}
FRAME_OF: dict[int, str] = {gid: frame for frame, gid in GID_OF.items()}
# Tiled gid 위 3비트는 뒤집기 표시다.
GID_MASK = 0x1FFFFFFF


def tileset_json() -> dict[str, Any]:
    """town.json `tilesets`에 넣는 그림 모음 타일셋."""
    tiles = []
    for i, frame in enumerate(OBJECT_FRAMES):
        w, h = OBJECT_CELLS[frame]
        tiles.append(
            {
                "id": i,
                "image": f"{IMAGE_DIR}/{frame}.png",
                "imagewidth": w * TILE,
                "imageheight": h * TILE,
                "properties": [{"name": "frame", "type": "string", "value": frame}],
            }
        )
    max_w = max(w for w, _ in OBJECT_CELLS.values()) * TILE
    max_h = max(h for _, h in OBJECT_CELLS.values()) * TILE
    return {
        "columns": 0,
        "firstgid": FIRSTGID,
        "grid": {"height": 1, "orientation": "orthogonal", "width": 1},
        "margin": 0,
        "name": NAME,
        "spacing": 0,
        "tilecount": len(OBJECT_FRAMES),
        "tileheight": max_h,
        "tiles": tiles,
        "tilewidth": max_w,
    }


def top_of(obj: dict[str, Any]) -> int:
    """객체 윗변 y(px). 타일 객체(gid)는 y가 아랫변이다."""
    return int(obj["y"]) - int(obj["height"]) if obj.get("gid") else int(obj["y"])


def frame_of_gid(gid: int) -> str | None:
    return FRAME_OF.get(gid & GID_MASK)


def to_tile_object(obj: dict[str, Any]) -> bool:
    """사각형 객체를 그림 타일 객체로 바꾸고, 이름이 빈 타일 객체에는 gid에서 이름을 채운다. 바꿨으면 True."""
    if obj.get("gid"):
        if obj.get("name"):
            return False
        frame = frame_of_gid(int(obj["gid"]))
        if frame is None:
            return False
        obj["name"] = frame
        return True
    gid = GID_OF.get(str(obj.get("name", "")))
    if gid is None:
        return False
    obj["gid"] = gid
    obj["y"] = int(obj["y"]) + int(obj["height"])
    return True
