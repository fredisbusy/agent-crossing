import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { TILE } from "../../../../src/game/map/fallback-map";
import {
  FACADE_HEIGHT,
  FACADE_LAYER,
  FACADE_STYLES,
  EAVE_BOTTOM,
  facadeGlassRects,
  facadeSeed as facadeSeedOf_,
  type FacadePlan,
  hasWindow,
  paintFacade,
  type Painter,
  planFacades,
} from "../../../../src/game/map/facade";
import { extractMapSprites } from "../../../../src/game/map/objects";

interface RawLayer {
  name: string;
  data?: number[];
  objects?: unknown[];
}
const town = JSON.parse(readFileSync(new URL("../../../../../shared/maps/town.json", import.meta.url), "utf8")) as {
  width: number;
  layers: RawLayer[];
};
const layer = (name: string): RawLayer => town.layers.find((l) => l.name === name) ?? { name };
const ground = layer("ground").data ?? [];
const isDoor = (tx: number, ty: number): boolean => ground[ty * town.width + tx] === TILE.door;
const plans = planFacades(extractMapSprites(layer(FACADE_LAYER).objects ?? []), isDoor);

const facadeSeedOf = (plan: FacadePlan): number => facadeSeedOf_(plan.name);

/** fillRect 호출을 모으는 가짜 캔버스. */
function recorder(): Painter & { rects: { color: string; x: number; y: number; w: number; h: number }[] } {
  const rects: { color: string; x: number; y: number; w: number; h: number }[] = [];
  return {
    rects,
    fillStyle: "",
    fillRect(x: number, y: number, w: number, h: number) {
      rects.push({ color: String(this.fillStyle), x, y, w, h });
    },
  };
}

describe("facade plan", () => {
  it("has one styled front per building with exactly one outside door", () => {
    expect(plans.map((p) => p.name).sort()).toEqual(Object.keys(FACADE_STYLES).sort());
    for (const plan of plans) {
      expect(plan.doorColumns).toHaveLength(1);
      expect(plan.columns).toBeGreaterThanOrEqual(10);
    }
  });

  it("puts the sign center on wall, not over the door or the corner posts", () => {
    for (const plan of plans) {
      const column = (plan.signCenterX - plan.x) / 16;
      expect(column).toBeGreaterThan(1);
      expect(column).toBeLessThan(plan.columns - 1);
      expect(plan.doorColumns.some((d) => Math.floor(column) === d && column % 1 !== 0)).toBe(false);
    }
  });

  it("gives buildings different roofs, walls, or window kinds", () => {
    const looks = new Set(plans.map((p) => `${p.style.roof}/${p.style.wall}/${p.style.kind}`));
    expect(looks.size).toBe(plans.length);
  });
});

describe("facade art", () => {
  const cafe = plans.find((p) => p.name === "Hobbs Cafe") as FacadePlan;

  it("paints only inside its columns×48 box", () => {
    for (const plan of plans) {
      const ctx = recorder();
      paintFacade(ctx, plan);
      expect(ctx.rects.length).toBeGreaterThan(50);
      for (const r of ctx.rects) {
        expect(r.x).toBeGreaterThanOrEqual(0);
        expect(r.y).toBeGreaterThanOrEqual(0);
        expect(r.x + r.w).toBeLessThanOrEqual(plan.columns * 16);
        expect(r.y + r.h).toBeLessThanOrEqual(FACADE_HEIGHT);
      }
    }
  });

  it("is deterministic for the same plan", () => {
    const a = recorder();
    const b = recorder();
    paintFacade(a, cafe);
    paintFacade(b, cafe);
    expect(a.rects).toEqual(b.rects);
  });

  it("never opens a window on the door or the corner columns", () => {
    for (const plan of plans) {
      expect(hasWindow(plan, 0, 0)).toBe(false);
      expect(hasWindow(plan, plan.columns - 1, 0)).toBe(false);
      for (const d of plan.doorColumns) expect(hasWindow(plan, d, 0)).toBe(false);
    }
  });

  it("hangs a striped awning only on shops", () => {
    const awningColor = cafe.style.awning?.[0];
    const ctx = recorder();
    paintFacade(ctx, cafe);
    expect(ctx.rects.some((r) => r.color === awningColor)).toBe(true);
    const house = plans.find((p) => p.style.kind === "house") as FacadePlan;
    expect(house.style.awning).toBeNull();
  });
});

describe("facade glass (night window lights)", () => {
  it("lights every window and the door, inside the front, below the eave", () => {
    for (const plan of plans) {
      const rects = facadeGlassRects(plan);
      const windows = Array.from({ length: plan.columns }, (_, c) => c).filter((c) => hasWindow(plan, c, facadeSeedOf(plan)));
      expect(rects).toHaveLength(windows.length + plan.doorColumns.length);
      for (const r of rects) {
        expect(r.x).toBeGreaterThanOrEqual(plan.x);
        expect(r.x + r.w).toBeLessThanOrEqual(plan.x + plan.columns * 16);
        expect(r.y).toBeGreaterThanOrEqual(plan.y + EAVE_BOTTOM);
        expect(r.y + r.h).toBeLessThanOrEqual(plan.y + FACADE_HEIGHT);
      }
    }
  });

  it("matches the glass the art paints", () => {
    const cafe = plans.find((p) => p.name === "Hobbs Cafe") as FacadePlan;
    const ctx = recorder();
    paintFacade(ctx, cafe);
    const painted = ctx.rects.filter((r) => r.color === "#f6d77a");
    for (const glass of facadeGlassRects(cafe)) {
      const local = { x: glass.x - cafe.x, y: glass.y - cafe.y, w: glass.w, h: glass.h };
      expect(painted).toContainEqual({ color: "#f6d77a", ...local });
    }
  });
});
