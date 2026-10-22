import { describe, expect, it } from "vitest";
import { createPosesWorld } from "../../src/mock/pose-scenario";

describe("poses 시나리오", () => {
  it("주민은 매 틱 같은 자리에 고정되고 결정론적이다", () => {
    const world = createPosesWorld();
    const first = world.next();
    const second = world.next();
    expect(first.residents.length).toBeGreaterThanOrEqual(10);
    expect(second.tick).toBe(first.tick + 1);
    expect(second.residents.map((r) => r.tile)).toEqual(first.residents.map((r) => r.tile));
    expect(first.residents.some((r) => r.utterance_text !== null)).toBe(true);
  });
});
