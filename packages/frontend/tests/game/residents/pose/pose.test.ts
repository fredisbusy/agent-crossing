import { describe, expect, it } from "vitest";
import type { MapSprite } from "../../../../src/game/map/objects";
import { classifyAction, type ActionInput } from "../../../../src/game/residents/pose/action-kind";
import { choosePose } from "../../../../src/game/residents/pose/pose";
import { SpotMap } from "../../../../src/game/residents/pose/spots";

function input(action: string | null, emoji: string | null = null, extra: Partial<ActionInput> = {}): ActionInput {
  return { action_description: action, emoji, talking: false, moving: false, ...extra };
}

describe("classifyAction", () => {
  it.each([
    ["sleeping in bed", null, "sleep"],
    ["침대에서 자는 중", null, "sleep"],
    ["부엌에서 요리하는 중", null, "cook"],
    ["cooking dinner", null, "cook"],
    ["이젤 앞에서 그림 그리는 중", null, "paint"],
    ["painting a landscape", null, "paint"],
    ["도서관에서 공부하는 중", null, "study"],
    ["attending class", null, "study"],
    ["책을 읽는 중", null, "read"],
    ["카페에서 커피를 마시는 중", null, "coffee"],
    ["맥주 한잔", null, "drink"],
    ["점심 식사", null, "eat"],
    ["시장에서 장보는 중", null, "shop"],
    ["기타 연주", null, "music"],
    ["정원에서 꽃에 물을 주는 중", null, "garden"],
    ["사무실에서 일하는 중", null, "work"],
    ["깊이 생각하는 중", null, "think"],
    ["이웃과 대화하는 중", null, "talk"],
    ["광장 쪽으로 걷는 중", null, "walk"],
    ["벤치에서 쉬는 중", null, "rest"],
  ] as const)("%s -> %s", (action, emoji, expected) => {
    expect(classifyAction(input(action, emoji))).toBe(expected);
  });

  it("uses the emoji when the text is only generic", () => {
    expect(classifyAction(input("광장에서 쉬는 중", "☕"))).toBe("coffee");
    expect(classifyAction(input(null, "🛒"))).toBe("shop");
    expect(classifyAction(input(null, "🎒"))).toBe("study");
  });

  it("prefers walking, then talking, over text", () => {
    expect(classifyAction(input("자는 중", null, { moving: true, talking: true }))).toBe("walk");
    expect(classifyAction(input("자는 중", null, { talking: true }))).toBe("talk");
  });

  it("returns null when nothing matches", () => {
    expect(classifyAction(input(null))).toBeNull();
    expect(classifyAction(input("???", "🪨"))).toBeNull();
  });
});

describe("SpotMap and choosePose", () => {
  const sprite = (frame: string, x: number, y: number, width: number, height: number): MapSprite => ({ frame, x, y, width, height });
  const spots = new SpotMap(
    [sprite("furn_chair_right", 128, 160, 16, 16), sprite("furn_bed", 16, 32, 16, 32), sprite("furn_sofa", 64, 64, 32, 16)],
    [sprite("bench_h", 448, 304, 32, 16)],
  );

  it("finds seats with the chair direction and spans multi-tile furniture", () => {
    expect(spots.spotAt(8, 10)).toEqual({ kind: "seat", facing: "right" });
    expect(spots.spotAt(4, 4)).toEqual({ kind: "seat", facing: "down" });
    expect(spots.spotAt(5, 4)).toEqual({ kind: "seat", facing: "down" });
    expect(spots.spotAt(29, 19)).toEqual({ kind: "seat", facing: "down" });
    expect(spots.spotAt(0, 0)).toBeNull();
  });

  it("maps both bed rows to the bed bottom", () => {
    expect(spots.spotAt(1, 2)).toEqual({ kind: "bed", bottomPx: 64 });
    expect(spots.spotAt(1, 3)).toEqual({ kind: "bed", bottomPx: 64 });
  });

  it("walking wins over everything", () => {
    expect(choosePose({ kind: "sleep", moving: true, spot: spots.spotAt(1, 2) }).act).toBe("walk");
  });

  it("sleeps only on a bed, sits on seats, otherwise follows the action", () => {
    expect(choosePose({ kind: "sleep", moving: false, spot: spots.spotAt(1, 2) }).act).toBe("sleep");
    expect(choosePose({ kind: "sleep", moving: false, spot: null }).act).toBe("idle");
    expect(choosePose({ kind: "rest", moving: false, spot: spots.spotAt(8, 10) })).toMatchObject({ act: "sit", facing: "right" });
    expect(choosePose({ kind: "cook", moving: false, spot: null }).act).toBe("work");
    expect(choosePose({ kind: "paint", moving: false, spot: null }).act).toBe("work");
    expect(choosePose({ kind: "talk", moving: false, spot: null }).act).toBe("talk");
    expect(choosePose({ kind: "rest", moving: false, spot: null }).act).toBe("idle");
  });
});
