import { describe, expect, it } from "vitest";
import { VILLAGER_LOOKS, villagerLookFor } from "../../../src/game/residents/looks";

describe("villagerLookFor", () => {
  it("is deterministic and spreads ids over the ten looks", () => {
    expect(VILLAGER_LOOKS).toHaveLength(10);
    expect(villagerLookFor("mochi")).toBe(villagerLookFor("mochi"));
    const seen = new Set(Array.from({ length: 200 }, (_, i) => villagerLookFor(`resident-${i}`)));
    expect(seen.size).toBe(10);
  });
});
