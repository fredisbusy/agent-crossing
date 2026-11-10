import { describe, expect, it } from "vitest";
import type { WorldSnapshot } from "@agent-crossing/shared";
import { appendUtterances, MAX_UTTERANCES_PER_RESIDENT } from "../../src/stores/utterance-history";

function snapshot(tick: number, text: string | null): WorldSnapshot {
  return {
    tick,
    sim_time: "2023-02-13T07:00:00Z",
    residents: [
      {
        resident_id: "a",
        display_name: "A",
        tile: { x: 0, y: 0 },
        location_path: "Town",
        action_description: null,
        emoji: null,
        utterance_text: text,
        mind_kind: null,
        current_plan_item: null,
      },
    ],
  };
}

describe("appendUtterances", () => {
  it("records new utterances newest first and ignores silence", () => {
    let history = appendUtterances({}, snapshot(1, "one"));
    history = appendUtterances(history, snapshot(2, null));
    history = appendUtterances(history, snapshot(3, "three"));
    expect(history.a.map((e) => e.text)).toEqual(["three", "one"]);
  });

  it("does not duplicate the same tick", () => {
    const once = appendUtterances({}, snapshot(1, "one"));
    expect(appendUtterances(once, snapshot(1, "one"))).toBe(once);
  });

  it("keeps only the latest few", () => {
    let history = {};
    for (let tick = 0; tick < MAX_UTTERANCES_PER_RESIDENT + 3; tick += 1) {
      history = appendUtterances(history, snapshot(tick, `t${tick}`));
    }
    expect(Object.values(history)[0]).toHaveLength(MAX_UTTERANCES_PER_RESIDENT);
  });
});
