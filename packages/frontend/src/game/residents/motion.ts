import type { ResidentSnapshot, TilePosition } from "@agent-crossing/shared";

interface Segment {
  from: TilePosition;
  to: TilePosition;
  startMs: number;
  durationMs: number;
}

/** 타일 좌표(소수 허용)에서 다음 스냅샷 타일까지 선형 보간한다. */
export function lerpTile(from: TilePosition, to: TilePosition, t: number): TilePosition {
  const clamped = Math.min(1, Math.max(0, t));
  return { x: from.x + (to.x - from.x) * clamped, y: from.y + (to.y - from.y) * clamped };
}

/** 한 스냅샷 사이에 걸어서 보간할 최대 거리(칸). 시뮬레이션은 한 틱에 한 칸만 움직인다. */
export const MAX_WALK_STEP_TILES = 1;

function manhattan(a: TilePosition, b: TilePosition): number {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

/**
 * 주민별 이동 구간을 추적한다. 시간은 호출자가 주입한다(결정론).
 * 직전 목표 칸에서 한 칸을 넘게 떨어진 위치를 받으면(재접속, 틱 누락) 걸어가는 보간 없이 순간이동한다.
 * 그래야 벽을 가로질러 미끄러지는 그림이 나오지 않는다.
 */
export class MotionTracker {
  private readonly segments = new Map<string, Segment>();

  /** 새 스냅샷을 받는다. 지금 그려지는 위치에서 새 타일까지 `durationMs` 동안 이동한다. */
  observe(residents: readonly ResidentSnapshot[], nowMs: number, durationMs: number): void {
    const alive = new Set<string>();
    for (const resident of residents) {
      alive.add(resident.resident_id);
      const previous = this.segments.get(resident.resident_id);
      const target = { ...resident.tile };
      if (!previous) {
        this.segments.set(resident.resident_id, { from: target, to: target, startMs: nowMs, durationMs });
        continue;
      }
      if (manhattan(previous.to, target) > MAX_WALK_STEP_TILES) {
        this.segments.set(resident.resident_id, { from: target, to: target, startMs: nowMs, durationMs });
        continue;
      }
      const current = this.positionAt(resident.resident_id, nowMs) ?? target;
      this.segments.set(resident.resident_id, { from: current, to: target, startMs: nowMs, durationMs });
    }
    for (const id of [...this.segments.keys()]) {
      if (!alive.has(id)) this.segments.delete(id);
    }
  }

  positionAt(id: string, nowMs: number): TilePosition | null {
    const segment = this.segments.get(id);
    if (!segment) return null;
    const progress = segment.durationMs <= 0 ? 1 : (nowMs - segment.startMs) / segment.durationMs;
    return lerpTile(segment.from, segment.to, progress);
  }
}
