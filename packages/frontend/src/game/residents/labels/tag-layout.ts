/** 이름표 한 장의 월드 좌표 사각형(가운데 x, 윗변 y)과 우선순위. */
export interface TagBox {
  id: string;
  x: number;
  top: number;
  width: number;
  height: number;
  /** 클수록 먼저 자리를 잡는다(선택된 주민 > 아래쪽 주민). */
  priority: number;
}

export interface TagOffset {
  dx: number;
  dy: number;
}

const GAP = 1;
/** 아래로 비키는 비용 배율. 이름표끼리는 옆을, 간판은 아래를 먼저 고른다. */
const TAG_DOWN_WEIGHT = 2;
const OBSTACLE_DOWN_WEIGHT = 0.5;

interface Candidate extends TagOffset {
  cost: number;
}

/** 이름표가 비켜야 하는 고정 사각형(월드 좌표). 건물 간판 등. */
export interface TagObstacle {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

type Rect = TagObstacle;

function rectOf(box: TagBox, offset: TagOffset): Rect {
  const left = box.x + offset.dx - box.width / 2;
  const top = box.top + offset.dy;
  return { left, right: left + box.width, top, bottom: top + box.height };
}

function overlaps(a: Rect, b: Rect): boolean {
  return a.left < b.right + GAP && b.left < a.right + GAP && a.top < b.bottom + GAP && b.top < a.bottom + GAP;
}

/**
 * 겹치는 이름표를 서로 덮지 않게 가로로 민다(우선순위가 높은 쪽은 그대로).
 * 옆으로 밀어도 안 되면 아래로 민다. `obstacles`(간판 등)는 먼저 자리를 잡은 것으로 보고 이름표가 비킨다.
 * 입력 순서와 무관하게 결정론적이다.
 */
export function resolveTagOffsets(boxes: readonly TagBox[], obstacles: readonly TagObstacle[] = []): Map<string, TagOffset> {
  const sorted = [...boxes].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  const placed: Rect[] = [...obstacles];
  const result = new Map<string, TagOffset>();
  for (const box of sorted) {
    const candidates: Candidate[] = [{ dx: 0, dy: 0, cost: 0 }];
    placed.forEach((other, index) => {
      const reach = (box.width + (other.right - other.left)) / 2 + GAP;
      const centerX = (other.left + other.right) / 2 - box.x;
      const down = other.bottom + GAP - box.top;
      // 이름표끼리는 옆이 싸다. 간판은 길어서 옆으로 비키면 주인과 멀어지니 바로 아래가 싸다.
      const downWeight = index < obstacles.length ? OBSTACLE_DOWN_WEIGHT : TAG_DOWN_WEIGHT;
      candidates.push({ dx: centerX + reach, dy: 0, cost: Math.abs(centerX + reach) });
      candidates.push({ dx: centerX - reach, dy: 0, cost: Math.abs(centerX - reach) });
      candidates.push({ dx: 0, dy: down, cost: Math.abs(down) * downWeight });
    });
    candidates.sort((a, b) => a.cost - b.cost);
    const free = candidates.find((c) => placed.every((p) => !overlaps(rectOf(box, c), p))) ?? candidates[0];
    placed.push(rectOf(box, free));
    result.set(box.id, { dx: free.dx, dy: free.dy });
  }
  return result;
}
