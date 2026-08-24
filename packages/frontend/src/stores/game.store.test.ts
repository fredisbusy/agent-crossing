import { beforeEach, describe, expect, it } from "vitest";
import { useGameStore } from "./game.store";

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
    useGameStore.getState().clearGameTextOverlay("interior:스토리하우스 도서관");
    expect(useGameStore.getState().gameTextOverlay.labels).toEqual([label]);

    useGameStore.getState().clearGameTextOverlay("world");
    expect(useGameStore.getState().gameTextOverlay).toEqual({
      owner: null,
      labels: [],
    });
  });
});
