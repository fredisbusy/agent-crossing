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

interface Rect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

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
 * 옆으로 밀어도 안 되면 아래로 민다. 입력 순서와 무관하게 결정론적이다.
 */
export function resolveTagOffsets(boxes: readonly TagBox[]): Map<string, TagOffset> {
  const sorted = [...boxes].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  const placed: Rect[] = [];
  const result = new Map<string, TagOffset>();
  for (const box of sorted) {
    const candidates: TagOffset[] = [{ dx: 0, dy: 0 }];
    for (const other of placed) {
      const reach = (box.width + (other.right - other.left)) / 2 + GAP;
      const centerX = (other.left + other.right) / 2 - box.x;
      candidates.push({ dx: centerX + reach, dy: 0 }, { dx: centerX - reach, dy: 0 });
      candidates.push({ dx: 0, dy: other.bottom + GAP - box.top });
    }
    candidates.sort((a, b) => Math.abs(a.dx) + Math.abs(a.dy) * 2 - (Math.abs(b.dx) + Math.abs(b.dy) * 2));
    const free = candidates.find((c) => placed.every((p) => !overlaps(rectOf(box, c), p))) ?? candidates[0];
    placed.push(rectOf(box, free));
    result.set(box.id, free);
  }
  return result;
}
