import type { SpatialAgentState } from "@agent-crossing/shared";
import { describe, expect, it } from "vitest";
import { isAgentInsideHome } from "./homeInterior";

function agent(currentAction: string): SpatialAgentState {
  return {
    agent_id: "jiho",
    name: "지호",
    tile_position: { x: 5, y: 15 },
    position: { x: 176, y: 496 },
    destination: "브라이어 코브 > 지호의 집",
    current_action: currentAction,
    plan: "지호의 집에서 쉰다.",
    route_remaining: 0,
    active_day: null,
    active_hourly: null,
    active_minute: null,
    day_plan: [],
    bubble_kind: "action",
    bubble_text: "",
  };
}

describe("home interior recognition", () => {
  it("recognizes a resident only after the explicit inside transition", () => {
    expect(isAgentInsideHome(agent("moving_to:지호의 집"), "지호의 집")).toBe(
      false,
    );
    expect(
      isAgentInsideHome(agent("arrived_at_door:지호의 집"), "지호의 집"),
    ).toBe(false);
    expect(isAgentInsideHome(agent("inside:지호의 집"), "지호의 집")).toBe(
      true,
    );
  });

  it("does not put a resident inside a different home", () => {
    expect(isAgentInsideHome(agent("inside:지호의 집"), "수진의 집")).toBe(
      false,
    );
  });
});
