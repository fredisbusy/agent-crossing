import { describe, expect, it } from "vitest";
import type { ResidentSnapshot } from "@agent-crossing/shared";
import { BUBBLE_DURATION_MS, BubbleTracker } from "../../../src/game/residents/bubbles";
import { lerpTile, MotionTracker } from "../../../src/game/residents/motion";

function resident(id: string, x: number, y: number, text: string | null = null): ResidentSnapshot {
  return {
    resident_id: id,
    display_name: id,
    tile: { x, y },
    location_path: "Town",
    action_description: null,
    emoji: null,
    utterance_text: text,
    mind_kind: null,
    current_plan_item: null,
  };
}

describe("lerpTile", () => {
  it("interpolates and clamps progress", () => {
    expect(lerpTile({ x: 0, y: 0 }, { x: 4, y: 2 }, 0.5)).toEqual({ x: 2, y: 1 });
    expect(lerpTile({ x: 0, y: 0 }, { x: 4, y: 2 }, 3)).toEqual({ x: 4, y: 2 });
    expect(lerpTile({ x: 0, y: 0 }, { x: 4, y: 2 }, -1)).toEqual({ x: 0, y: 0 });
  });
});

describe("MotionTracker", () => {
  it("places new residents immediately", () => {
    const tracker = new MotionTracker();
    tracker.observe([resident("a", 3, 3)], 0, 1000);
    expect(tracker.positionAt("a", 0)).toEqual({ x: 3, y: 3 });
  });

  it("moves toward the new tile over the tick duration", () => {
    const tracker = new MotionTracker();
    tracker.observe([resident("a", 0, 0)], 0, 1000);
    tracker.observe([resident("a", 1, 0)], 0, 1000);
    expect(tracker.positionAt("a", 500)).toEqual({ x: 0.5, y: 0 });
    expect(tracker.positionAt("a", 1000)).toEqual({ x: 1, y: 0 });
  });

  it("restarts from the currently drawn position when interrupted", () => {
    const tracker = new MotionTracker();
    tracker.observe([resident("a", 0, 0)], 0, 1000);
    tracker.observe([resident("a", 1, 0)], 0, 1000);
    tracker.observe([resident("a", 1, 1)], 500, 1000);
    expect(tracker.positionAt("a", 500)).toEqual({ x: 0.5, y: 0 });
    expect(tracker.positionAt("a", 1500)).toEqual({ x: 1, y: 1 });
  });

  it("teleports instead of sliding when a snapshot jumps more than one tile", () => {
    const tracker = new MotionTracker();
    tracker.observe([resident("a", 0, 0)], 0, 1000);
    tracker.observe([resident("a", 3, 2)], 0, 1000);
    expect(tracker.positionAt("a", 0)).toEqual({ x: 3, y: 2 });
    expect(tracker.positionAt("a", 500)).toEqual({ x: 3, y: 2 });
  });

  it("forgets residents that disappear", () => {
    const tracker = new MotionTracker();
    tracker.observe([resident("a", 0, 0)], 0, 1000);
    tracker.observe([], 10, 1000);
    expect(tracker.positionAt("a", 10)).toBeNull();
  });
});

describe("BubbleTracker", () => {
  it("shows the utterance for a few seconds", () => {
    const tracker = new BubbleTracker();
    tracker.observe([resident("a", 0, 0, "hello")], 100);
    expect(tracker.textAt("a", 100)).toBe("hello");
    expect(tracker.textAt("a", 100 + BUBBLE_DURATION_MS - 1)).toBe("hello");
    expect(tracker.textAt("a", 100 + BUBBLE_DURATION_MS)).toBeNull();
  });

  it("keeps the bubble when later snapshots are silent", () => {
    const tracker = new BubbleTracker();
    tracker.observe([resident("a", 0, 0, "hello")], 0);
    tracker.observe([resident("a", 0, 0, null)], 1000);
    expect(tracker.textAt("a", 1500)).toBe("hello");
  });
});
