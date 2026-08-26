import type { DashboardEvent, PlanItemState } from "@agent-crossing/shared";
import { describe, expect, it } from "vitest";
import {
  planScheduleIssues,
  railEvents,
  selectedAgentEvents,
} from "./dashboardViewModel";

const events = [
  { sequence: 1, agent_id: "haeun" },
  { sequence: 2, agent_id: "jiho" },
] as DashboardEvent[];

describe("dashboard view model", () => {
  it("keeps the selected-agent log independent from the rail filter", () => {
    expect(railEvents(events, "jiho").map((event) => event.sequence)).toEqual([
      2,
    ]);
    expect(
      selectedAgentEvents(events, "haeun").map((event) => event.sequence),
    ).toEqual([1]);
  });

  it("detects day-plan gaps and overlaps", () => {
    const plans = [
      ["09:00:00", "10:00:00"],
      ["10:30:00", "11:00:00"],
      ["10:45:00", "12:00:00"],
    ].map(
      ([start, end]) =>
        ({
          start_time: `2026-08-26T${start}`,
          end_time: `2026-08-26T${end}`,
          location: "브라이어 코브",
          action_content: "테스트 일정",
        }) satisfies PlanItemState,
    );

    expect(planScheduleIssues(plans)).toEqual([
      "일정 1–2 사이 공백",
      "일정 2–3 시간이 겹침",
    ]);
  });
});
