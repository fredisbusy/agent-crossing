import { describe, expect, it } from "vitest";
import { createMockWorld } from "../../src/mock/mock-world";
import { renderStateToText } from "../../src/qa/state-text";

function textAfter(seed: number, ticks: number): string {
  const world = createMockWorld(seed);
  let snapshot = world.next();
  for (let i = 0; i < ticks; i += 1) snapshot = world.next();
  return renderStateToText({
    snapshot,
    connection: "mock",
    camera: { scroll_x: 0, scroll_y: 0, zoom: 2 },
    bubbleOf: (id) => (id === "mochi" ? snapshot.residents[0].utterance_text : null),
  });
}

describe("renderStateToText", () => {
  it("gives the same text for the same seed", () => {
    expect(textAfter(11, 30)).toBe(textAfter(11, 30));
  });

  it("includes time, tick, residents, connection and camera", () => {
    const parsed = JSON.parse(textAfter(11, 5));
    expect(parsed.tick).toBe(5);
    expect(parsed.connection).toBe("mock");
    expect(parsed.camera.zoom).toBe(2);
    expect(parsed.residents[0]).toHaveProperty("id");
    expect(parsed.residents[0].tile).toHaveLength(2);
    expect(parsed.sim_time).toMatch(/^2023-02-13T/);
  });

  it("handles a missing snapshot", () => {
    const parsed = JSON.parse(renderStateToText({ snapshot: null, connection: "connecting", camera: null, bubbleOf: () => null }));
    expect(parsed.residents).toEqual([]);
    expect(parsed.tick).toBeNull();
  });
});
