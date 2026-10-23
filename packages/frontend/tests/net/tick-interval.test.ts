import { describe, expect, it } from "vitest";
import {
  MAX_TICK_INTERVAL_MS,
  MIN_TICK_INTERVAL_MS,
  nextTickIntervalMs,
  TickIntervalEstimator,
} from "../../src/net/tick-interval";

describe("nextTickIntervalMs", () => {
  it("표본이 같으면 그대로다", () => {
    expect(nextTickIntervalMs(1000, 1000)).toBe(1000);
  });

  it("표본 쪽으로 조금씩 움직인다", () => {
    const next = nextTickIntervalMs(1000, 2000);
    expect(next).toBeGreaterThan(1000);
    expect(next).toBeLessThan(2000);
  });

  it("터무니없는 표본은 범위 안으로 자른다", () => {
    expect(nextTickIntervalMs(1000, 1e9)).toBeLessThanOrEqual(MAX_TICK_INTERVAL_MS);
    expect(nextTickIntervalMs(MIN_TICK_INTERVAL_MS, -50)).toBe(MIN_TICK_INTERVAL_MS);
    expect(nextTickIntervalMs(1000, Number.NaN)).toBe(1000);
  });
});

describe("TickIntervalEstimator", () => {
  it("첫 스냅샷은 초기값을 유지한다", () => {
    expect(new TickIntervalEstimator().observe(500)).toBe(1000);
  });

  it("도착 간격이 일정하면 그 값으로 수렴한다", () => {
    const estimator = new TickIntervalEstimator();
    let now = 0;
    let last = 0;
    for (let i = 0; i < 40; i += 1) {
      now += 250;
      last = estimator.observe(now);
    }
    expect(last).toBeCloseTo(250, 0);
  });

  it("버린 도착 다음 표본은 간격으로 치지 않는다", () => {
    const estimator = new TickIntervalEstimator();
    estimator.observe(0);
    estimator.discard();
    expect(estimator.observe(60_000)).toBe(1000);
    expect(estimator.observe(60_250)).toBeLessThan(1000);
  });
});
