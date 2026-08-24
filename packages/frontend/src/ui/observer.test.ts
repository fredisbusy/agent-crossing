import type { SpatialAgentState } from "@agent-crossing/shared";
import { describe, expect, it } from "vitest";
import {
  buildMainEventView,
  residentDestinationLabel,
  residentPlanLabel,
  residentStatusLabel,
} from "./observer";

function agent(overrides: Partial<SpatialAgentState> = {}): SpatialAgentState {
  return {
    agent_id: "jiho",
    name: "Jiho Park",
    tile_position: { x: 1, y: 2 },
    position: { x: 32, y: 64 },
    destination: null,
    current_action: "idle:waiting",
    plan: "차분하게 하루를 준비한다",
    route_remaining: 0,
    active_day: null,
    active_hourly: null,
    active_minute: null,
    day_plan: [],
    bubble_kind: "action",
    bubble_text: "",
    ...overrides,
  };
}

describe("resident presentation", () => {
  it.each([
    ["moving_to:cafe", "이동 중"],
    ["planning_route:cafe", "경로 계산 중"],
    ["blocked:cafe", "이동 불가"],
    ["idle:waiting", "대기 중"],
    ["at:cafe", "활동 중"],
    ["unknown", "상태 확인 중"],
  ])("maps %s to %s", (action, label) => {
    expect(residentStatusLabel(action, "live")).toBe(label);
  });

  it("does not fabricate a plaza destination", () => {
    expect(residentDestinationLabel(agent(), "live")).toBe("목적지 없음");
    expect(
      residentDestinationLabel(
        agent({ destination: "Briar Cove > Story House" }),
        "live",
      ),
    ).toBe("Story House");
  });

  it("prefers the active minute plan over fallbacks", () => {
    expect(
      residentPlanLabel(
        agent({
          bubble_text: "말풍선",
          active_minute: {
            start_time: "2026-08-24T10:00:00+09:00",
            end_time: "2026-08-24T10:10:00+09:00",
            location: "Briar Cove > Story House",
            action_content: "책을 정리한다",
          },
        }),
      ),
    ).toBe("책을 정리한다");
  });
});

describe("main event presentation", () => {
  it("derives progress from the authoritative active-minute time window", () => {
    const view = buildMainEventView(
      agent({
        active_minute: {
          start_time: "2026-08-24T10:00:00+09:00",
          end_time: "2026-08-24T10:10:00+09:00",
          location: "Briar Cove > Story House",
          action_content: "도서관 서가를 정리한다",
        },
      }),
      "2026-08-24T10:05:00+09:00",
    );

    expect(view).toEqual({
      title: "도서관 서가를 정리한다",
      description: "Jiho Park · Story House",
      progressPercent: 50,
      progressLabel: "일정 진행 · 50%",
    });
  });

  it("does not present an expired schedule as the current event", () => {
    const scheduledAgent = agent({
      active_minute: {
        start_time: "2026-08-24T10:00:00+09:00",
        end_time: "2026-08-24T10:10:00+09:00",
        location: "Briar Cove > Story House",
        action_content: "책을 정리한다",
      },
    });

    expect(
      buildMainEventView(scheduledAgent, "2026-08-24T11:00:00+09:00"),
    ).toEqual({
      title: "Jiho Park의 현재 활동",
      description: "대기 중 · Story House",
      progressPercent: 0,
      progressLabel: "새 일정 동기화 중",
    });
  });
});
