"""8비트 RGBA PNG 읽기·쓰기(비인터레이스만). 맵 편집용 그림을 만드는 스크립트가 외부 의존 없이 쓴다."""

import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
RGBA = 6
CHANNELS = 4


class Image:
    """RGBA 픽셀 버퍼. `pixels`는 줄마다 width*4 바이트."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height * CHANNELS)

    def crop(self, x: int, y: int, w: int, h: int) -> "Image":
        out = Image(w, h)
        for row in range(h):
            start = ((y + row) * self.width + x) * CHANNELS
            out.pixels[row * w * CHANNELS : (row + 1) * w * CHANNELS] = self.pixels[start : start + w * CHANNELS]
        return out

    def paste(self, src: "Image", x: int, y: int) -> None:
        """알파를 섞어 얹는다(0이면 건너뛰고, 255면 덮는다)."""
        for row in range(src.height):
            for col in range(src.width):
                tx, ty = x + col, y + row
                if not (0 <= tx < self.width and 0 <= ty < self.height):
                    continue
                s = (row * src.width + col) * CHANNELS
                d = (ty * self.width + tx) * CHANNELS
                alpha = src.pixels[s + 3]
                if alpha == 0:
                    continue
                for c in range(3):
                    self.pixels[d + c] = (src.pixels[s + c] * alpha + self.pixels[d + c] * (255 - alpha)) // 255
                self.pixels[d + 3] = max(self.pixels[d + 3], alpha)

    def fill(self, x: int, y: int, w: int, h: int, rgba: tuple[int, int, int, int]) -> None:
        dot = Image(1, 1)
        dot.pixels[:] = bytes(rgba)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.paste(dot, xx, yy)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def read_png(path: Path) -> Image:
    data = path.read_bytes()
    if data[:8] != SIGNATURE:
        raise ValueError(f"PNG가 아니다: {path}")
    pos, idat = 8, b""
    width = height = 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color != RGBA or interlace:
                raise ValueError(f"8비트 RGBA 비인터레이스 PNG만 읽는다: {path}")
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * CHANNELS
    image = Image(width, height)
    prev = bytearray(stride)
    for row in range(height):
        kind = raw[row * (stride + 1)]
        line = bytearray(raw[row * (stride + 1) + 1 : (row + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - CHANNELS] if i >= CHANNELS else 0
            up = prev[i]
            corner = prev[i - CHANNELS] if i >= CHANNELS else 0
            add = (0, left, up, (left + up) // 2, _paeth(left, up, corner))[kind]
            line[i] = (line[i] + add) & 0xFF
        image.pixels[row * stride : (row + 1) * stride] = line
        prev = line
    return image


def write_png(image: Image, path: Path) -> None:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    stride = image.width * CHANNELS
    raw = b"".join(b"\x00" + bytes(image.pixels[r * stride : (r + 1) * stride]) for r in range(image.height))
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, RGBA, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
