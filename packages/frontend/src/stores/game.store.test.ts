import { beforeEach, describe, expect, it } from "vitest";
import { useGameStore } from "./game.store";
import type {
  SpatialAgentState,
  SpatialWorldSnapshot,
} from "@agent-crossing/shared";

function agent(agentId: string): SpatialAgentState {
  return {
    agent_id: agentId,
    name: agentId,
    tile_position: { x: 1, y: 1 },
    position: { x: 32, y: 32 },
    destination: null,
    current_action: "idle",
    plan: "쉰다",
    route_remaining: 0,
    active_day: null,
    active_hourly: null,
    active_minute: null,
    day_plan: [],
    bubble_kind: "action",
    bubble_text: "쉰다",
  };
}

function snapshot(agents: SpatialAgentState[]): SpatialWorldSnapshot {
  return {
    session_id: "session",
    revision: 1,
    map_id: "briar-cove",
    agents,
    current_time: "2026-08-26T09:00:00",
    turn: 1,
    scheduler_running: true,
    planning_error: null,
  };
}

describe("game store UI commands", () => {
  beforeEach(() => {
    useGameStore.setState(useGameStore.getInitialState(), true);
  });

  it("emits a new follow request when the same resident is selected again", () => {
    const initialRequestId = useGameStore.getState().followRequestId;

    useGameStore.getState().selectAgent("sujin");
    useGameStore.getState().selectAgent("sujin");

    expect(useGameStore.getState().selectedAgentId).toBe("sujin");
    expect(useGameStore.getState().followRequestId).toBe(initialRequestId + 2);
  });

  it("removes disabled residents and selects the first remaining resident", () => {
    useGameStore
      .getState()
      .setSnapshot(snapshot([agent("jiho"), agent("sujin")]));
    useGameStore.getState().selectAgent("sujin");

    useGameStore.getState().setSnapshot(snapshot([agent("jiho")]));

    expect(useGameStore.getState().hasWorldSnapshot).toBe(true);
    expect(Object.keys(useGameStore.getState().agents)).toEqual(["jiho"]);
    expect(useGameStore.getState().selectedAgentId).toBe("jiho");
  });

  it("tracks the active scene and dismisses interaction feedback", () => {
    useGameStore.getState().setSceneContext({
      kind: "interior",
      name: "스토리하우스 도서관",
    });
    useGameStore.getState().showInteractionNotice({
      title: "Community Board",
      description: "주민 행동: 공지 읽기",
    });

    expect(useGameStore.getState().sceneContext).toEqual({
      kind: "interior",
      name: "스토리하우스 도서관",
    });
    expect(useGameStore.getState().interactionNotice?.title).toBe(
      "Community Board",
    );

    useGameStore.getState().dismissInteractionNotice();
    expect(useGameStore.getState().interactionNotice).toBeNull();
  });

  it("only clears text overlays owned by the active scene", () => {
    const label = {
      id: "location:스토리하우스 도서관",
      text: "스토리하우스 도서관",
      left: 120,
      top: 80,
      tone: "location" as const,
      anchor: "center" as const,
    };

    useGameStore.getState().setGameTextOverlay("world", [label]);
    useGameStore
      .getState()
      .clearGameTextOverlay("interior:스토리하우스 도서관");
    expect(useGameStore.getState().gameTextOverlay.labels).toEqual([label]);

    useGameStore.getState().clearGameTextOverlay("world");
    expect(useGameStore.getState().gameTextOverlay).toEqual({
      owner: null,
      labels: [],
    });
  });
});
