"""Tiled 편집용 의미 타일 8종 PNG(`packages/shared/maps/town-tiles.png`)를 만든다 (SPEC §15).

게임은 이 PNG를 쓰지 않는다. 프런트 `tileset-art.ts`가 같은 그림을 코드로 그리고, 픽셀 팩이 있으면
자동타일로 다시 그린다. 이 파일은 Tiled에서 무엇을 칠하는지 보이게 하는 용도다.
팔레트·사각형은 `packages/frontend/src/game/map/tileset-art.ts`와 맞춘다. 외부 의존 없음.

사용: python3 scripts/maps/export_tileset.py [출력 경로]
"""

import struct
import sys
import zlib
from pathlib import Path

TILE = 16
COUNT = 8
Rect = tuple[str, int, int, int, int]  # 색, x, y, w, h (타일 안 좌표)

PALETTE = {
    "grass": "#8fd18a",
    "grassDark": "#7bc277",
    "road": "#e8cf9c",
    "roadDark": "#d6b97f",
    "floor": "#f3e2c0",
    "floorLine": "#e2cc9f",
    "wall": "#a9705a",
    "wallDark": "#8a5846",
    "water": "#74c2e8",
    "waterLight": "#b4e3f5",
    "wood": "#c28a52",
    "woodDark": "#9a6a3a",
    "door": "#7a4a32",
    "knob": "#f6d365",
    "trunk": "#7a5230",
    "leaf": "#4aa564",
    "leafDark": "#378a50",
}

# gid 1..8: 풀, 길, 마루, 벽, 물, 가구, 문, 나무
TILES: tuple[tuple[Rect, ...], ...] = (
    (("grass", 0, 0, 16, 16), ("grassDark", 3, 4, 2, 1), ("grassDark", 10, 11, 2, 1), ("grassDark", 12, 3, 1, 2)),
    (("road", 0, 0, 16, 16), ("roadDark", 2, 3, 2, 2), ("roadDark", 9, 9, 3, 2), ("roadDark", 12, 2, 1, 1)),
    (("floor", 0, 0, 16, 16), ("floorLine", 0, 7, 16, 1), ("floorLine", 7, 0, 1, 7), ("floorLine", 3, 8, 1, 8)),
    (("wall", 0, 0, 16, 16), ("wallDark", 0, 5, 16, 1), ("wallDark", 0, 11, 16, 1), ("wallDark", 4, 0, 1, 5),
     ("wallDark", 11, 6, 1, 5)),
    (("water", 0, 0, 16, 16), ("waterLight", 2, 4, 5, 1), ("waterLight", 9, 11, 5, 1)),
    (("floor", 0, 0, 16, 16), ("woodDark", 0, 3, 16, 11), ("wood", 0, 3, 16, 8), ("woodDark", 2, 6, 4, 2)),
    (("wall", 0, 0, 16, 16), ("door", 3, 1, 10, 15), ("wood", 4, 2, 8, 14), ("knob", 10, 9, 2, 2)),
    (("grass", 0, 0, 16, 16), ("trunk", 7, 10, 3, 6), ("leafDark", 2, 2, 12, 10), ("leaf", 3, 1, 10, 9)),
)  # fmt: skip


def rgb(hex_color: str) -> bytes:
    return bytes.fromhex(hex_color[1:])


def paint() -> list[bytearray]:
    rows = [bytearray(TILE * COUNT * 3) for _ in range(TILE)]
    for index, rects in enumerate(TILES):
        for color, x, y, w, h in rects:
            pixel = rgb(PALETTE[color])
            for yy in range(y, y + h):
                for xx in range(index * TILE + x, index * TILE + x + w):
                    rows[yy][xx * 3 : xx * 3 + 3] = pixel
    return rows


def png(rows: list[bytearray], width: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    header = struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main() -> None:
    default = Path(__file__).resolve().parents[2] / "packages/shared/maps/town-tiles.png"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.write_bytes(png(paint(), TILE * COUNT))


if __name__ == "__main__":
    main()
