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

const ZERO_OFFSET: TagOffset = Object.freeze({ dx: 0, dy: 0 });

function rectOf(box: TagBox, offset: TagOffset): Rect {
  const left = box.x + offset.dx - box.width / 2;
  const top = box.top + offset.dy;
  return { left, right: left + box.width, top, bottom: top + box.height };
}

/** 이름표를 (dx, dy)만큼 옮겼을 때 사각형 `b`와 겹치는가. 객체를 만들지 않는다. */
function boxOverlaps(box: TagBox, dx: number, dy: number, b: Rect): boolean {
  const left = box.x + dx - box.width / 2;
  const top = box.top + dy;
  return left < b.right + GAP && b.left < left + box.width + GAP && top < b.bottom + GAP && b.top < top + box.height + GAP;
}

function boxesOverlap(a: TagBox, b: TagBox): boolean {
  const aLeft = a.x - a.width / 2;
  const bLeft = b.x - b.width / 2;
  return aLeft < bLeft + b.width + GAP && bLeft < aLeft + a.width + GAP && a.top < b.top + b.height + GAP && b.top < a.top + a.height + GAP;
}

/** 아무 이름표도 다른 이름표·장애물과 겹치지 않는가(겹침이 없으면 모두 제자리다). */
function isClear(boxes: readonly TagBox[], obstacles: readonly TagObstacle[]): boolean {
  for (let i = 0; i < boxes.length; i += 1) {
    for (const obstacle of obstacles) if (boxOverlaps(boxes[i], 0, 0, obstacle)) return false;
    for (let j = i + 1; j < boxes.length; j += 1) if (boxesOverlap(boxes[i], boxes[j])) return false;
  }
  return true;
}

/**
 * 겹치는 이름표를 서로 덮지 않게 가로로 민다(우선순위가 높은 쪽은 그대로).
 * 옆으로 밀어도 안 되면 아래로 민다. `obstacles`(간판 등)는 먼저 자리를 잡은 것으로 보고 이름표가 비킨다.
 * 입력 순서와 무관하게 결정론적이다.
 */
export function resolveTagOffsets(boxes: readonly TagBox[], obstacles: readonly TagObstacle[] = []): Map<string, TagOffset> {
  if (isClear(boxes, obstacles)) {
    const still = new Map<string, TagOffset>();
    for (const box of boxes) still.set(box.id, ZERO_OFFSET);
    return still;
  }
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
    const free = candidates.find((c) => placed.every((p) => !boxOverlaps(box, c.dx, c.dy, p))) ?? candidates[0];
    placed.push(rectOf(box, free));
    result.set(box.id, { dx: free.dx, dy: free.dy });
  }
  return result;
}

function sameBoxes(a: readonly TagBox[], b: readonly TagBox[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    const p = a[i];
    const q = b[i];
    if (p.id !== q.id || p.x !== q.x || p.top !== q.top || p.width !== q.width || p.height !== q.height || p.priority !== q.priority) {
      return false;
    }
  }
  return true;
}

function sameObstacles(a: readonly TagObstacle[], b: readonly TagObstacle[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].left !== b[i].left || a[i].right !== b[i].right || a[i].top !== b[i].top || a[i].bottom !== b[i].bottom) return false;
  }
  return true;
}

/**
 * `resolveTagOffsets`의 직전 결과를 기억한다. 이름표 목록(주민 위치·크기=줌 반영)과 장애물이 그대로면 다시 계산하지 않는다.
 * `resolve`가 돌려주는 맵은 다음 호출 전까지 바뀌지 않는다.
 */
export class TagLayoutCache {
  private boxes: readonly TagBox[] = [];
  private obstacles: readonly TagObstacle[] = [];
  private result: Map<string, TagOffset> | null = null;
  /** 실제로 다시 계산한 횟수(테스트·진단용). */
  computeCount = 0;

  /** 값이 바뀌었으면 새로 계산한 결과를, 같으면 이전 결과를 돌려준다. `changed`는 결과가 새것인지 알려준다. */
  resolve(boxes: readonly TagBox[], obstacles: readonly TagObstacle[]): { offsets: Map<string, TagOffset>; changed: boolean } {
    if (this.result && sameBoxes(this.boxes, boxes) && sameObstacles(this.obstacles, obstacles)) {
      return { offsets: this.result, changed: false };
    }
    this.boxes = boxes;
    this.obstacles = obstacles;
    this.result = resolveTagOffsets(boxes, obstacles);
    this.computeCount += 1;
    return { offsets: this.result, changed: true };
  }
}
