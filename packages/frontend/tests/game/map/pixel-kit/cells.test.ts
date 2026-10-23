import { describe, expect, it } from "vitest";
import atlas from "../../../../src/assets/pixel-kit/atlas.tp.json";
import { buildFallbackMap } from "../../../../src/game/map/fallback-map";
import { TILE } from "../../../../src/tiled";
import { planPixelKit } from "../../../../src/game/map/pixel-kit";
import { neighborMask } from "../../../../src/game/map/pixel-kit/cells";
import type { TiledTileLayer } from "../../../../src/tiled";

const frames = new Set(Object.keys(atlas.frames));
const names = (plan: ReturnType<typeof planPixelKit>) => plan.ground.map((d) => d.frame);

describe("pixel-kit plan", () => {
  it("uses only frames that exist in the atlas", () => {
    const map = buildFallbackMap();
    const ground = map.layers.find((l): l is TiledTileLayer => l.type === "tilelayer" && l.name === "ground");
    const plan = planPixelKit(ground?.data ?? [], map.width, map.height);
    expect(plan.ground.length).toBeGreaterThan(0);
    const missing = [...plan.ground, ...plan.props].map((d) => d.frame).filter((name) => !frames.has(name));
    expect(missing).toEqual([]);
  });

  it("lays grass under each road and joins roads past the map edge", () => {
    const plan = planPixelKit([TILE.road, TILE.road, TILE.grass], 3, 1);
    expect(names(plan).filter((n) => n.startsWith("grass"))).toHaveLength(3);
    const isRoad = (x: number, y: number) => x < 0 || y !== 0 || x <= 1;
    expect(neighborMask(isRoad, 1, 0)).toBe(1 | 4 | 8);
  });

  it("joins walls through doors and picks the door kind from the wall line", () => {
    // 가로벽: 벽 문 벽 / 세로벽: 벽 위아래로 문
    const row = planPixelKit([TILE.wall, TILE.door, TILE.wall], 3, 1);
    expect(names(row)).toEqual(["wall_m2", "door_h", "wall_m8"]);
    const column = planPixelKit([TILE.wall, TILE.door, TILE.wall], 1, 3);
    expect(names(column)).toEqual(["wall_m4", "door_v", "wall_m1"]);
  });

  it("shades the floor right under a wall face", () => {
    const plan = planPixelKit([TILE.wall, TILE.floor], 1, 2);
    expect(names(plan)).toContain("shade_wall");
  });

  it("pairs furniture into two-tile pieces and leaves a single one as a plant", () => {
    const plan = planPixelKit([TILE.furniture, TILE.furniture, TILE.furniture], 3, 1);
    const pieces = names(plan).filter((n) => n.startsWith("furn_"));
    expect(pieces).toHaveLength(2);
    expect(pieces[0]).not.toBe("furn_plant");
    expect(pieces[1]).toBe("furn_plant");
  });

  it("draws the pond as a water autotile over grass", () => {
    const plan = planPixelKit([TILE.water, TILE.water], 2, 1);
    expect(names(plan).filter((n) => n.startsWith("water_m2") || n.startsWith("water_m8"))).toHaveLength(2);
  });

  it("shrinks a tree to a bush when it would cover a building", () => {
    const open = planPixelKit([TILE.grass, TILE.grass, TILE.tree], 1, 3);
    const blocked = planPixelKit([TILE.wall, TILE.tree], 1, 2);
    expect(open.props[0]?.frame.startsWith("tree_town")).toBe(true);
    expect(blocked.props[0]?.frame.startsWith("bush")).toBe(true);
  });
});
