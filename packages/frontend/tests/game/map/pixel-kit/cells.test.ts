import { describe, expect, it } from "vitest";
import atlas from "../../../../src/assets/pixel-kit/atlas.tp.json";
import { buildFallbackMap, TILE } from "../../../../src/game/map/fallback-map";
import { planPixelKit } from "../../../../src/game/map/pixel-kit";
import { roadMask } from "../../../../src/game/map/pixel-kit/cells";
import type { TiledTileLayer } from "../../../../src/game/map/tiled-types";

const frames = new Set(Object.keys(atlas.frames));

describe("pixel-kit plan", () => {
  it("uses only frames that exist in the atlas", () => {
    const map = buildFallbackMap();
    const ground = map.layers.find((l): l is TiledTileLayer => l.type === "tilelayer" && l.name === "ground");
    const plan = planPixelKit(ground?.data ?? [], map.width, map.height);
    expect(plan.ground.length).toBeGreaterThan(0);
    const missing = [...plan.ground, ...plan.props].map((d) => d.frame).filter((name) => !frames.has(name));
    expect(missing).toEqual([]);
  });

  it("leaves buildings and water to the base tiles", () => {
    const plan = planPixelKit([TILE.wall, TILE.water, TILE.floor, TILE.door], 4, 1);
    expect(plan).toEqual({ ground: [], props: [] });
  });

  it("lays grass under each road and joins roads past the map edge", () => {
    const plan = planPixelKit([TILE.road, TILE.road, TILE.grass], 3, 1);
    expect(plan.ground.filter((d) => d.frame.startsWith("grass"))).toHaveLength(3);
    const isRoad = (x: number, y: number) => x < 0 || y !== 0 || x <= 1;
    expect(roadMask(isRoad, 1, 0)).toBe(1 | 4 | 8);
  });

  it("shrinks a tree to a bush when it would cover a building", () => {
    const open = planPixelKit([TILE.grass, TILE.tree, TILE.grass, TILE.grass], 1, 4);
    const blocked = planPixelKit([TILE.wall, TILE.tree], 1, 2);
    expect(open.props[0]?.frame.startsWith("tree")).toBe(true);
    expect(blocked.props[0]?.frame.startsWith("bush")).toBe(true);
  });
});
