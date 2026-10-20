import { describe, expect, it } from "vitest";
import type { WorldSnapshot } from "@agent-crossing/shared";
import { MockFeed } from "../../src/mock/mock-feed";
import { createMockWorld } from "../../src/mock/mock-world";
import { FALLBACK_MAP_HEIGHT, FALLBACK_MAP_WIDTH } from "../../src/town-layout";

function collect(seed: number, ticks: number): WorldSnapshot[] {
  const world = createMockWorld(seed);
  return Array.from({ length: ticks }, () => world.next());
}

describe("mock world", () => {
  it("is deterministic for the same seed", () => {
    expect(collect(7, 80)).toEqual(collect(7, 80));
  });

  it("moves at most one tile per tick and stays on the map", () => {
    const snapshots = collect(1, 200);
    snapshots.forEach((snapshot, index) => {
      expect(snapshot.tick).toBe(index);
      for (const resident of snapshot.residents) {
        expect(resident.tile.x).toBeGreaterThanOrEqual(0);
        expect(resident.tile.x).toBeLessThan(FALLBACK_MAP_WIDTH);
        expect(resident.tile.y).toBeGreaterThanOrEqual(0);
        expect(resident.tile.y).toBeLessThan(FALLBACK_MAP_HEIGHT);
        if (index === 0) continue;
        const before = snapshots[index - 1].residents.find((r) => r.resident_id === resident.resident_id);
        const distance = Math.abs(resident.tile.x - (before?.tile.x ?? 0)) + Math.abs(resident.tile.y - (before?.tile.y ?? 0));
        expect(distance).toBeLessThanOrEqual(1);
      }
    });
  });

  it("makes someone speak now and then", () => {
    const spoken = collect(3, 200).flatMap((s) => s.residents).filter((r) => r.utterance_text);
    expect(spoken.length).toBeGreaterThan(0);
  });
});

describe("MockFeed.advance", () => {
  it("emits one snapshot per tick interval once paused", () => {
    const ticks: number[] = [];
    const feed = new MockFeed(5, 1000);
    feed.start({ onSnapshot: (s) => ticks.push(s.tick), onStatus: () => {} });
    feed.pause();
    feed.advance(2500);
    feed.advance(500);
    expect(ticks).toEqual([0, 1, 2, 3]);
    feed.stop();
  });
});
