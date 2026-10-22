import { describe, expect, it } from "vitest";
import { containZoom, coverZoom, fitZoom, paddedBounds } from "../../../src/game/scenes/camera-fit";

const MAP_W = 1024;
const MAP_H = 640;

describe("camera fit", () => {
  it("shows the whole town on a desktop pane instead of cropping both ends", () => {
    // 1440×900 창에서 주민 시트를 뺀 지도 칸.
    const zoom = fitZoom(1152, 840, MAP_W, MAP_H);
    expect(zoom).toBe(containZoom(1152, 840, MAP_W, MAP_H));
    expect(MAP_W * zoom).toBeLessThanOrEqual(1152);
    expect(MAP_H * zoom).toBeLessThanOrEqual(840);
    expect(zoom).toBeLessThan(coverZoom(1152, 840, MAP_W, MAP_H));
  });

  it("still covers the screen on a tall phone, where a full view would leave huge bands", () => {
    expect(fitZoom(390, 720, MAP_W, MAP_H)).toBe(coverZoom(390, 720, MAP_W, MAP_H));
  });

  it("keeps zoom on 1/8 steps", () => {
    for (const [w, h] of [[1152, 840], [1520, 1020], [390, 720], [800, 500]]) {
      const zoom = fitZoom(w, h, MAP_W, MAP_H);
      expect(Math.round(zoom * 8)).toBe(zoom * 8);
    }
  });

  it("pads bounds evenly so a smaller-than-screen map sits in the middle", () => {
    const b = paddedBounds(1152, 840, MAP_W, MAP_H, 1.125);
    expect(b.x).toBe(0);
    expect(b.y).toBeCloseTo(-(840 / 1.125 - MAP_H) / 2);
    expect(b.y * 2 + b.height).toBeCloseTo(MAP_H);
    expect(paddedBounds(390, 720, MAP_W, MAP_H, 1.125)).toEqual({ x: 0, y: 0, width: MAP_W, height: MAP_H });
  });
});
