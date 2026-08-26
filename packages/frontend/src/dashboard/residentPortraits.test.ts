import { describe, expect, it } from "vitest";

import { residentPortraitUrl } from "./residentPortraits";

describe("residentPortraitUrl", () => {
  it.each(["haeun", "jiho", "jungwoo", "minji", "sujin", "taeo"])(
    "maps %s to its checked-in portrait",
    (agentId) => {
      expect(residentPortraitUrl(agentId)).toBe(`/portraits/${agentId}.png`);
    },
  );

  it("normalizes agent ids and keeps unknown residents on the fallback", () => {
    expect(residentPortraitUrl("Haeun")).toBe("/portraits/haeun.png");
    expect(residentPortraitUrl("new-resident")).toBeNull();
  });
});
