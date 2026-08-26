import type { SpatialWorldSnapshot } from "@agent-crossing/shared";
import { describe, expect, it } from "vitest";
import {
  loadLastWorldSnapshot,
  saveLastWorldSnapshot,
  type WorldSnapshotStorage,
} from "./useWorldStream";

function snapshot(): SpatialWorldSnapshot {
  return {
    session_id: "session-1",
    revision: 7,
    map_id: "briar-cove",
    current_time: "2026-08-26T09:00:00",
    turn: 4,
    scheduler_running: true,
    planning_error: null,
    agents: [
      {
        agent_id: "jiho",
        name: "지호",
        tile_position: { x: 17, y: 16 },
        position: { x: 560, y: 528 },
        destination: "브라이어 코브 > 마을 광장",
        current_action: "moving_to:브라이어 코브 > 마을 광장",
        plan: "마을 광장으로 이동한다.",
        route_remaining: 3,
        active_day: null,
        active_hourly: null,
        active_minute: null,
        day_plan: [],
        bubble_kind: "action",
        bubble_text: "마을 광장으로 이동한다.",
      },
    ],
  };
}

function memoryStorage(): WorldSnapshotStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

describe("world stream last-position cache", () => {
  it("restores the last authoritative snapshot after a connection failure", () => {
    const storage = memoryStorage();
    const lastSnapshot = snapshot();

    saveLastWorldSnapshot(storage, lastSnapshot);

    expect(loadLastWorldSnapshot(storage)).toEqual(lastSnapshot);
  });

  it("ignores malformed cached snapshots instead of showing default positions", () => {
    const storage: WorldSnapshotStorage = {
      getItem: () => '{"agents":"invalid"}',
      setItem: () => undefined,
    };

    expect(loadLastWorldSnapshot(storage)).toBeNull();
  });
});
