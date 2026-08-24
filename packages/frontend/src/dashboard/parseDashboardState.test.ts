import { describe, expect, it } from "vitest";
import { parseDashboardState } from "./parseDashboardState";

const fixture = {
  world: {
    available: true,
    revision: 12,
    turn: 8,
    current_time: "2026-08-24T09:00:00",
    scheduler_running: true,
    cognitive_active: false,
    effective_time_step_seconds: 300,
    cognitive_runtime_error: null,
    planning_error: null,
  },
  agents: [
    {
      agent_id: "Jiho",
      name: "Jiho Park",
      current_action: "at:The Honey Cup",
      destination: "Briar Cove > The Honey Cup",
      tile_position: { x: 3, y: 5 },
      route_remaining: 0,
      bubble_kind: "thought",
      bubble_text: "오늘 계획을 점검한다.",
      current_plan_context: ["커피를 마신다"],
      active_day: null,
      active_hourly: null,
      active_minute: null,
      day_plan: [],
      reflection_status: { accumulated_importance: 42, threshold: 150 },
      relationships: [
        {
          target_agent_id: "Sujin",
          target_name: "Sujin Lee",
          affinity_score: null,
          measurement: "not_modeled",
          summary: "Jiho는 Sujin을 친구 이상으로 좋아한다.",
          evidence: [
            {
              source: "persona",
              content: "Jiho는 Sujin을 친구 이상으로 좋아한다.",
              memory_id: null,
              node_type: null,
              importance: null,
              created_at: null,
            },
          ],
        },
      ],
      memories: [
        {
          id: 1,
          node_type: "OBSERVATION",
          citations: null,
          content: "수진을 카페에서 보았다.",
          created_at: "2026-08-24T08:55:00",
          last_accessed_at: "2026-08-24T08:55:00",
          importance: 5,
        },
      ],
    },
  ],
  events: [],
  latest_sequence: 0,
};

describe("parseDashboardState", () => {
  it("accepts a valid diagnostics snapshot", () => {
    const parsed = parseDashboardState(fixture);
    expect(parsed?.agents[0]?.memories[0]?.content).toBe(
      "수진을 카페에서 보았다.",
    );
    expect(parsed?.world.revision).toBe(12);
    expect(parsed?.agents[0]?.relationships[0]?.summary).toBe(
      "Jiho는 Sujin을 친구 이상으로 좋아한다.",
    );
  });

  it("rejects malformed memories instead of rendering invented data", () => {
    const malformed = structuredClone(fixture);
    malformed.agents[0].memories[0].importance = "high" as never;
    expect(parseDashboardState(malformed)).toBeNull();
  });

  it("rejects malformed relationship evidence", () => {
    const malformed = structuredClone(fixture);
    malformed.agents[0].relationships[0].evidence[0].memory_id = "one" as never;
    expect(parseDashboardState(malformed)).toBeNull();
  });
});
