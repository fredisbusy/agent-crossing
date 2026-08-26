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
      current_action: "at:허니컵 카페",
      destination: "브라이어 코브 > 허니컵 카페",
      current_location_path: "브라이어 코브 > 허니컵 카페",
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
          measurement: "modeled_v1",
          metrics: {
            familiarity: 42,
            trust: 18,
            affinity: 27,
            tension: 4,
            romantic_interest: 12,
          },
          status_label: "알아가는 관계",
          revision: 3,
          updated_at: "2026-08-24T08:56:00",
          last_interaction_at: "2026-08-24T08:56:00",
          summary: "Jiho는 Sujin을 친구 이상으로 좋아한다.",
          summary_status: "available",
          evidence_total: 1,
          has_more_evidence: false,
          recent_events: [
            {
              id: "a62f46ee-d15d-5d91-bbc7-933d3782a09e",
              event_type: "DIALOGUE_COMPLETED",
              occurred_at: "2026-08-24T08:56:00",
              familiarity_delta: 2,
              trust_delta: 0,
              affinity_delta: 2,
              tension_delta: 0,
              romantic_interest_delta: 0,
              rule_version: "relationship-v1",
            },
          ],
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

  it("rejects relationship metrics outside their canonical range", () => {
    const malformed = structuredClone(fixture);
    malformed.agents[0].relationships[0].metrics.romantic_interest = 101;
    expect(parseDashboardState(malformed)).toBeNull();
  });

  it("rejects negative relationship counters and invalid timestamps", () => {
    const malformed = structuredClone(fixture);
    malformed.agents[0].relationships[0].revision = -1;
    malformed.agents[0].relationships[0].updated_at = "not-a-date";
    expect(parseDashboardState(malformed)).toBeNull();
  });
});
