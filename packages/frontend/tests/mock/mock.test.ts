import { describe, expect, it } from "vitest";
import type { WorldSnapshot } from "@agent-crossing/shared";
import { MockFeed } from "../../src/mock/mock-feed";
import { createMockWorld } from "../../src/mock/mock-world";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { fallbackWalkGrid } from "../../src/mock/mock-world";
import {
  FALLBACK_MAP_HEIGHT,
  FALLBACK_MAP_WIDTH,
  findPath,
  isWalkable,
  walkGridFromTiled,
  type WalkGrid,
} from "../../src/town-layout";

const TOWN_JSON = fileURLToPath(new URL("../../../shared/maps/town.json", import.meta.url));

function realTownGrid(): WalkGrid {
  const grid = walkGridFromTiled(JSON.parse(readFileSync(TOWN_JSON, "utf-8")));
  if (grid === null) throw new Error("town.json을 통행 격자로 읽지 못했다");
  return grid;
}

function expectNeverOnBlockedTile(grid: WalkGrid, seed: number, ticks: number): void {
  const world = createMockWorld(seed, grid);
  let previous: WorldSnapshot | null = null;
  for (let index = 0; index < ticks; index += 1) {
    const snapshot = world.next();
    for (const resident of snapshot.residents) {
      expect(isWalkable(grid, resident.tile.x, resident.tile.y)).toBe(true);
      const before = previous?.residents.find((r) => r.resident_id === resident.resident_id);
      if (before) {
        const distance = Math.abs(resident.tile.x - before.tile.x) + Math.abs(resident.tile.y - before.tile.y);
        expect(distance).toBeLessThanOrEqual(1);
      }
    }
    previous = snapshot;
  }
}

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

  it("never steps onto walls, water, furniture or trees of the fallback map", () => {
    expectNeverOnBlockedTile(fallbackWalkGrid(), 11, 600);
  });

  it("never steps onto blocked tiles of the real town map and visits several places", () => {
    const grid = realTownGrid();
    expect(grid.places.length).toBeGreaterThanOrEqual(18);
    expectNeverOnBlockedTile(grid, 4, 1500);
    const world = createMockWorld(4, grid);
    const visited = new Set<string>();
    for (let index = 0; index < 1500; index += 1) {
      for (const resident of world.next().residents) visited.add(resident.location_path);
    }
    expect(visited.size).toBeGreaterThan(4);
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

describe("walk grid", () => {
  it("finds a path that goes around walls and refuses blocked goals", () => {
    const grid = realTownGrid();
    const [from, to] = [grid.places[0].tile, grid.places[grid.places.length - 1].tile];
    const path = findPath(grid, from, to);
    expect(path).not.toBeNull();
    for (const step of path ?? []) expect(isWalkable(grid, step.x, step.y)).toBe(true);
    const wall = grid.blocked.findIndex((blocked) => blocked);
    expect(findPath(grid, from, { x: wall % grid.width, y: Math.floor(wall / grid.width) })).toBeNull();
  });
});
