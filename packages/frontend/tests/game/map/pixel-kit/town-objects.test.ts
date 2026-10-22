import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import atlas from "../../../../src/assets/pixel-kit/atlas.tp.json";
import { TILE } from "../../../../src/game/map/fallback-map";
import { extractLocationAreas } from "../../../../src/game/map/locations";
import { extractMapSprites } from "../../../../src/game/map/objects";
import { planPixelKit } from "../../../../src/game/map/pixel-kit";
import { birdPose, butterflyPose } from "../../../../src/game/map/pixel-kit/critters";
import { planMapObjects } from "../../../../src/game/map/pixel-kit/object-plan";
import { placeStyleAt } from "../../../../src/game/map/pixel-kit/place-style";
import { clampSignCenter, layoutSign, planSigns } from "../../../../src/game/map/pixel-kit/signs";
import { EAVE_BOTTOM, FACADE_LAYER, planFacades } from "../../../../src/game/map/facade";

interface RawLayer {
  name: string;
  data?: number[];
  objects?: unknown[];
}
const town = JSON.parse(readFileSync(new URL("../../../../../shared/maps/town.json", import.meta.url), "utf8")) as {
  width: number;
  height: number;
  layers: RawLayer[];
};
const layer = (name: string): RawLayer => town.layers.find((l) => l.name === name) ?? { name };
const areas = extractLocationAreas(layer("locations").objects ?? []);
const furniture = extractMapSprites(layer("furniture").objects ?? []);
const decor = extractMapSprites(layer("decor").objects ?? []);
const ground = layer("ground").data ?? [];
const frames = new Set(Object.keys(atlas.frames));
const facades = planFacades(extractMapSprites(layer(FACADE_LAYER).objects ?? []), (tx, ty) => ground[ty * town.width + tx] === TILE.door);

describe("map objects", () => {
  it("reads Tiled tile objects (gid) with y at the bottom edge", () => {
    const [tile, rect] = extractMapSprites([
      { name: "furn_bed", x: 16, y: 64, width: 16, height: 32, gid: 20 },
      { name: "furn_bed", x: 16, y: 32, width: 16, height: 32 },
    ]);
    expect(tile).toEqual({ frame: "furn_bed", x: 16, y: 32, width: 16, height: 32 });
    expect(rect).toEqual(tile);
  });

  it("keeps every town object inside the map and on a known frame", () => {
    for (const sprite of [...furniture, ...decor]) {
      expect(sprite.y).toBeGreaterThanOrEqual(0);
      expect(sprite.y + sprite.height).toBeLessThanOrEqual(town.height * 16);
      expect(sprite.frame === "light" || frames.has(sprite.frame)).toBe(true);
    }
  });
});

describe("place style", () => {
  const styleIn = (path: string, dx = 1, dy = 1) => {
    const area = areas.find((a) => a.location_path === path);
    if (!area) throw new Error(path);
    return placeStyleAt(areas, area.x + dx * 16 + 8, area.y + dy * 16 + 8);
  };

  it("picks wall and floor by building (contract E)", () => {
    expect(styleIn("Smallville > Hobbs Cafe", 8, 1)).toEqual({ floor: "floor_tile", wall: "wall_cream" });
    expect(styleIn("Smallville > The Willows Market")).toEqual({ floor: "floor_stone", wall: "wall_cream" });
    expect(styleIn("Smallville > Oak Hill College", 4, 1)).toEqual({ floor: "floor_study", wall: "wall_brick" });
    expect(styleIn("Smallville > The Rose and Crown Pub")).toEqual({ floor: "floor_dark", wall: "wall_brick" });
    expect(styleIn("Smallville > Lin Family House", 3, 1)).toEqual({ floor: "floor_wood", wall: "wall" });
  });

  it("lays carpet in bedrooms and falls back outside buildings", () => {
    expect(styleIn("Smallville > Lin Family House > Bedroom").floor).toBe("floor_carpet");
    expect(styleIn("Smallville > Dorm for Oak Hill College > Klaus's Room").floor).toBe("floor_carpet");
    expect(placeStyleAt(areas, 8, 8)).toEqual({ floor: "floor_wood", wall: "wall" });
  });

  it("plans town frames per building and cobbles the square", () => {
    const plan = planPixelKit(ground, town.width, town.height, { areas, furniture, decor });
    const names = new Set(plan.ground.map((d) => d.frame));
    expect([...names].some((n) => n.startsWith("wall_brick_m"))).toBe(true);
    expect([...names].some((n) => n.startsWith("wall_cream_m"))).toBe(true);
    expect(names.has("floor_dark")).toBe(true);
    expect(names.has("cobble")).toBe(true);
    const square = areas.find((a) => a.location_path === "Smallville > Town Square");
    const roadCell = plan.ground.find((d) => square && d.x === square.x && d.y === square.y);
    expect(roadCell?.frame.startsWith("grass") || roadCell?.frame.startsWith("cobble")).toBe(true);
    expect(plan.ground.some((d) => d.frame.startsWith("furn_shelf"))).toBe(false);
    expect(plan.ground.every((d) => frames.has(d.frame))).toBe(true);
    expect(TILE.road).toBe(2);
  });
});

describe("map objects", () => {
  it("only references atlas frames (except light)", () => {
    const missing = [...furniture, ...decor].map((s) => s.frame).filter((f) => f !== "light" && !frames.has(f));
    expect(missing).toEqual([]);
  });

  it("bakes rugs and flowers, y-sorts the rest, and skips light", () => {
    const plan = planMapObjects(furniture, decor);
    expect(plan.baked.every((b) => /^(rug_|mat_door|flower_bed_|lily_pad|reeds|tilled)/.test(b.frame))).toBe(true);
    expect(plan.sprites.some((s) => s.frame === "light")).toBe(false);
    const bench = decor.find((d) => d.frame === "bench_h");
    const planned = plan.sprites.find((s) => s.frame === "bench_h");
    expect(planned?.depth).toBe((bench?.y ?? 0) + (bench?.height ?? 0));
    expect(plan.sprites.find((s) => s.frame === "fountain_0")?.anim).toBe("fountain");
  });

  it("keeps beds at their map rectangle so sleepers line up", () => {
    const plan = planMapObjects(furniture, decor);
    const beds = plan.sprites.filter((s) => s.frame.startsWith("furn_bed"));
    const rects = furniture.filter((f) => f.frame.startsWith("furn_bed"));
    expect(beds.map((b) => [b.x, b.y])).toEqual(rects.map((r) => [r.x, r.y]));
  });
});

describe("signs", () => {
  it("makes one sign per building and widens in 8px steps", () => {
    const signs = planSigns(areas);
    expect(signs).toHaveLength(9);
    expect(signs.every((s) => frames.has(s.icon))).toBe(true);
    const narrow = layoutSign(10);
    const wide = layoutSign(90);
    expect(narrow.width).toBe(8 + narrow.middleCount * 8);
    expect(wide.middleCount).toBeGreaterThan(narrow.middleCount);
    expect(wide.textX + 90 + 2).toBeLessThanOrEqual(wide.width - 4 + 0.001);
  });

  it("stands every sign on its building's eave, inside the front", () => {
    const signs = planSigns(areas, facades);
    expect(signs).toHaveLength(9);
    for (const sign of signs) {
      const facade = facades.find((f) => f.name === sign.label);
      if (!facade) throw new Error(sign.label);
      expect(sign.below).toBe(false);
      expect(sign.edgeY).toBe(facade.y + EAVE_BOTTOM);
      expect(sign.bounds).toEqual([facade.x, facade.x + facade.columns * 16]);
    }
  });

  it("keeps a sign inside its front when it fits, and centers it when it does not", () => {
    expect(clampSignCenter(10, 40, [0, 176])).toBe(20);
    expect(clampSignCenter(170, 40, [0, 176])).toBe(156);
    expect(clampSignCenter(90, 40, [0, 176])).toBe(90);
    expect(clampSignCenter(10, 200, [0, 176])).toBe(88);
    expect(clampSignCenter(10, 40, null)).toBe(10);
  });
});

describe("critters", () => {
  it("is deterministic for a seed and time", () => {
    expect(birdPose(7, 5000)).toEqual(birdPose(7, 5000));
    expect(butterflyPose(7, 5000)).toEqual(butterflyPose(7, 5000));
    const frameNames = [birdPose(3, 0).frame, birdPose(3, 99999).frame, butterflyPose(3, 0).frame];
    expect(frameNames.every((f) => frames.has(f))).toBe(true);
  });
});
