export interface TilePoint {
  x: number;
  y: number;
}

export interface TileRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** 사각형이 칸(또는 점) (x, y)를 덮는지. 오른쪽·아래 끝은 포함하지 않는다. */
export function rectContains(rect: TileRect, x: number, y: number): boolean {
  return x >= rect.x && x < rect.x + rect.width && y >= rect.y && y < rect.y + rect.height;
}

/** (x, y)를 덮는 영역 중 가장 작은 것. 크기가 같으면 먼저 나온 것. 없으면 null. */
export function smallestAreaAt<T>(areas: readonly T[], x: number, y: number, rectOf: (area: T) => TileRect): T | null {
  let best: T | null = null;
  let bestSize = Infinity;
  for (const area of areas) {
    const rect = rectOf(area);
    if (!rectContains(rect, x, y)) continue;
    const size = rect.width * rect.height;
    if (best === null || size < bestSize) {
      best = area;
      bestSize = size;
    }
  }
  return best;
}
