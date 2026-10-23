import { describe, expect, it } from "vitest";
import { resolveTagOffsets, TagLayoutCache, type TagBox } from "../../../src/game/residents/labels/tag-layout";

const box = (id: string, x: number, top: number, priority: number): TagBox => ({ id, x, top, width: 40, height: 14, priority });

describe("resolveTagOffsets", () => {
  it("겹치지 않으면 그대로 둔다", () => {
    const out = resolveTagOffsets([box("a", 0, 0, 1), box("b", 100, 0, 2)]);
    expect(out.get("a")).toEqual({ dx: 0, dy: 0 });
    expect(out.get("b")).toEqual({ dx: 0, dy: 0 });
  });

  it("겹치면 우선순위 낮은 쪽을 비켜 서로 덮지 않게 한다", () => {
    const out = resolveTagOffsets([box("upper", 0, 0, 1), box("lower", 10, 10, 2)]);
    expect(out.get("lower")).toEqual({ dx: 0, dy: 0 });
    const moved = out.get("upper");
    expect(moved).not.toEqual({ dx: 0, dy: 0 });
    const upperLeft = 0 - 20 + (moved?.dx ?? 0);
    const upperRight = upperLeft + 40;
    const upperBottom = 14 + (moved?.dy ?? 0);
    const sideBySide = upperRight <= 10 - 20 || upperLeft >= 10 + 20;
    expect(sideBySide || upperBottom <= 10).toBe(true);
  });
});

describe("resolveTagOffsets with obstacles", () => {
  it("moves a tag off a sign instead of covering it", () => {
    const sign = { left: -60, right: 60, top: 10, bottom: 28 };
    const out = resolveTagOffsets([box("tom", 0, 12, 1)], [sign]);
    const moved = out.get("tom") ?? { dx: 0, dy: 0 };
    const left = -20 + moved.dx;
    const top = 12 + moved.dy;
    const clear = left + 40 <= sign.left || left >= sign.right || top + 14 <= sign.top || top >= sign.bottom;
    expect(clear).toBe(true);
  });

  it("prefers dropping below a long sign over sliding far sideways", () => {
    const out = resolveTagOffsets([box("tom", -30, 12, 1)], [{ left: -60, right: 200, top: 10, bottom: 28 }]);
    expect(out.get("tom")).toEqual({ dx: 0, dy: 28 + 1 - 12 });
  });

  it("leaves tags that do not touch any sign where they are", () => {
    const out = resolveTagOffsets([box("far", 300, 0, 1)], [{ left: -60, right: 60, top: 10, bottom: 28 }]);
    expect(out.get("far")).toEqual({ dx: 0, dy: 0 });
  });
});

describe("TagLayoutCache", () => {
  it("입력이 같으면 다시 계산하지 않는다", () => {
    const cache = new TagLayoutCache();
    const first = cache.resolve([box("a", 0, 0, 1), box("b", 10, 10, 2)], []);
    const second = cache.resolve([box("a", 0, 0, 1), box("b", 10, 10, 2)], []);
    expect(first.changed).toBe(true);
    expect(second.changed).toBe(false);
    expect(second.offsets).toBe(first.offsets);
    expect(cache.computeCount).toBe(1);
  });

  it("위치나 장애물이 바뀌면 다시 계산한다", () => {
    const cache = new TagLayoutCache();
    cache.resolve([box("a", 0, 0, 1)], []);
    expect(cache.resolve([box("a", 5, 0, 1)], []).changed).toBe(true);
    expect(cache.resolve([box("a", 5, 0, 1)], [{ left: 0, right: 10, top: 0, bottom: 10 }]).changed).toBe(true);
    expect(cache.computeCount).toBe(3);
  });

  it("겹침이 없을 때와 있을 때의 결과가 직접 계산과 같다", () => {
    const cache = new TagLayoutCache();
    const boxes = [box("a", 0, 0, 1), box("b", 10, 10, 2), box("c", 200, 0, 3)];
    expect([...cache.resolve(boxes, []).offsets]).toEqual([...resolveTagOffsets(boxes, [])]);
  });
});
