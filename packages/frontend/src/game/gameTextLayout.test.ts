import { describe, expect, it } from "vitest";
import type { GameTextOverlay } from "./gameText";
import { resolveCharacterTextOverlaps } from "./gameTextLayout";

describe("resolveCharacterTextOverlaps", () => {
  it("stacks character bubbles instead of allowing them to overlap", () => {
    const bubble = (id: string): GameTextOverlay => ({
      id,
      text: "같은 위치에서 이야기하는 주민",
      left: 200,
      top: 160,
      tone: "bubble",
      anchor: "bottom",
      maxWidth: 220,
    });

    const resolved = resolveCharacterTextOverlaps([
      bubble("agent:jiho:bubble"),
      bubble("agent:sujin:bubble"),
    ]);

    expect(resolved[0]?.top).toBe(160);
    expect(resolved[1]?.top).toBeLessThanOrEqual(122);
  });

  it("does not move unrelated location labels", () => {
    const label: GameTextOverlay = {
      id: "location:스토리하우스 도서관",
      text: "스토리하우스 도서관",
      left: 200,
      top: 160,
      tone: "location",
      anchor: "center",
    };

    expect(resolveCharacterTextOverlaps([label])).toEqual([label]);
  });
});
