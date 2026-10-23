import { DEFAULT_TICK_INTERVAL_MS } from "./feed";

/** 보간 길이의 하한·상한(ms). 재접속 공백이나 연달아 온 스냅샷이 보간을 망치지 않게 한다. */
export const MIN_TICK_INTERVAL_MS = 100;
export const MAX_TICK_INTERVAL_MS = 5000;
/** 새 표본이 추정값에 반영되는 비율(지수이동평균). */
export const TICK_INTERVAL_EMA_ALPHA = 0.3;

function clampInterval(ms: number): number {
  return Math.min(MAX_TICK_INTERVAL_MS, Math.max(MIN_TICK_INTERVAL_MS, ms));
}

/** 스냅샷 도착 간격 표본 하나를 반영한 새 추정값. 순수 함수. */
export function nextTickIntervalMs(previousMs: number, sampleMs: number): number {
  if (!Number.isFinite(sampleMs)) return clampInterval(previousMs);
  const blended = previousMs + TICK_INTERVAL_EMA_ALPHA * (clampInterval(sampleMs) - previousMs);
  return clampInterval(blended);
}

/** 스냅샷이 도착한 시각들로 틱 간격을 추정한다. 시각은 호출자가 주입한다(결정론). */
export class TickIntervalEstimator {
  private lastArrivalMs: number | null = null;
  private estimateMs: number;

  constructor(initialMs: number = DEFAULT_TICK_INTERVAL_MS) {
    this.estimateMs = clampInterval(initialMs);
  }

  /** 스냅샷이 `nowMs`에 도착했다. 갱신된 추정값(보간 길이)을 돌려준다. */
  observe(nowMs: number): number {
    if (this.lastArrivalMs !== null) this.estimateMs = nextTickIntervalMs(this.estimateMs, nowMs - this.lastArrivalMs);
    this.lastArrivalMs = nowMs;
    return this.estimateMs;
  }

  get intervalMs(): number {
    return this.estimateMs;
  }
}
