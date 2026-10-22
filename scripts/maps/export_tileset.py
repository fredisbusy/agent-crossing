"""Tiled 편집용 그림을 픽셀 팩 아틀라스에서 뽑는다 (SPEC §15).

- `packages/shared/maps/town-tiles.png`: 의미 타일 8종(gid 1..8)을 게임과 비슷한 픽셀 그림으로.
  게임은 이 PNG를 쓰지 않는다. 길·벽·물은 게임에서 이웃에 따라 자동타일로 다시 그려진다.
- `packages/shared/maps/objects/<프레임>.png`: 가구·장식 그림 모음 타일셋(`town_object_tiles.py`) 그림.

아틀라스: `packages/frontend/src/assets/pixel-kit/atlas.png`·`atlas.tp.json`. 외부 의존 없음.
사용: python3 scripts/maps/export_tileset.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from png_io import Image, read_png, write_png  # noqa: E402
from town_object_tiles import IMAGE_DIR, OBJECT_CELLS, OBJECT_FRAMES, TILE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ATLAS_DIR = ROOT / "packages/frontend/src/assets/pixel-kit"
MAPS_DIR = ROOT / "packages/shared/maps"

# gid 1..8: 풀, 길, 마루, 벽, 물, 가구 밑, 문, 나무. 프레임을 차례로 겹쳐 한 칸을 만든다.
GROUND_LAYERS: tuple[tuple[str, ...], ...] = (
    ("grass_spring",),
    ("grass_spring", "dirt_m15"),
    ("floor_wood",),
    ("wall_m15",),
    ("grass_spring", "water_m15"),
    ("floor_wood",),
    ("floor_wood", "door_h"),
    ("grass_spring", "sapling"),
)
FURNITURE_GID_INDEX = 5
# 가구 밑(막힌 바닥)은 마루 위에 사선 빗금으로 표시한다(실제 가구 그림은 객체가 보여 준다).
HATCH = (60, 40, 30, 150)
LIGHT_GLOW = (255, 214, 102, 255)
LIGHT_RIM = (200, 140, 40, 255)


def frame_image(atlas: Image, frames: dict[str, dict[str, dict[str, int]]], name: str) -> Image:
    f = frames[name]["frame"]
    return atlas.crop(f["x"], f["y"], f["w"], f["h"])


def ground_tiles(atlas: Image, frames: dict[str, dict[str, dict[str, int]]]) -> Image:
    sheet = Image(TILE * len(GROUND_LAYERS), TILE)
    for index, layers in enumerate(GROUND_LAYERS):
        for name in layers:
            sheet.paste(frame_image(atlas, frames, name), index * TILE, 0)
    ox = FURNITURE_GID_INDEX * TILE
    for i in range(-TILE, TILE, 4):
        for d in range(TILE):
            if 0 <= i + d < TILE:
                sheet.fill(ox + i + d, d, 1, 1, HATCH)
    return sheet


def light_marker() -> Image:
    """가로등 빛 자리(`light`)는 그림 프레임이 없어 노란 원으로 표시한다."""
    image = Image(TILE, TILE)
    center = (TILE - 1) / 2
    for y in range(TILE):
        for x in range(TILE):
            r = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
            if r <= 4:
                image.fill(x, y, 1, 1, LIGHT_GLOW)
            elif r <= 5:
                image.fill(x, y, 1, 1, LIGHT_RIM)
    return image


def main() -> None:
    atlas = read_png(ATLAS_DIR / "atlas.png")
    frames = json.loads((ATLAS_DIR / "atlas.tp.json").read_text(encoding="utf-8"))["frames"]
    write_png(ground_tiles(atlas, frames), MAPS_DIR / "town-tiles.png")
    for frame in OBJECT_FRAMES:
        image = frame_image(atlas, frames, frame) if frame in frames else light_marker()
        w, h = OBJECT_CELLS[frame]
        if (image.width, image.height) != (w * TILE, h * TILE):
            raise ValueError(f"{frame} 그림 크기 {image.width}x{image.height}가 칸 {w}x{h}와 다르다.")
        write_png(image, MAPS_DIR / IMAGE_DIR / f"{frame}.png")
    print(f"편집용 그림: town-tiles.png + {IMAGE_DIR}/ {len(OBJECT_FRAMES)}장")


if __name__ == "__main__":
    main()
