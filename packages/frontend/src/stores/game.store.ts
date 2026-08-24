import type {
  SpatialAgentState,
  SpatialWorldSnapshot,
} from "@agent-crossing/shared";
import { create } from "zustand";
import type { GameTextOverlay } from "../game/gameText";

export type ConnectionStatus = "connecting" | "live" | "offline";
export type SceneContext =
  | { kind: "world" }
  | { kind: "interior"; name: string };

export interface WorldInteractionNotice {
  title: string;
  description: string;
}

interface GameTextOverlayState {
  owner: string | null;
  labels: readonly GameTextOverlay[];
}

interface GameState {
  revision: number;
  mapId: string | null;
  agents: Record<string, SpatialAgentState>;
  connectionStatus: ConnectionStatus;
  currentTime: string | null;
  turn: number;
  schedulerRunning: boolean;
  planningError: string | null;
  selectedAgentId: string;
  followRequestId: number;
  sceneContext: SceneContext;
  interactionNotice: WorldInteractionNotice | null;
  gameTextOverlay: GameTextOverlayState;
  setSnapshot: (snapshot: SpatialWorldSnapshot) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  selectAgent: (agentId: string) => void;
  setSceneContext: (sceneContext: SceneContext) => void;
  showInteractionNotice: (notice: WorldInteractionNotice) => void;
  dismissInteractionNotice: () => void;
  setGameTextOverlay: (
    owner: string,
    labels: readonly GameTextOverlay[],
  ) => void;
  clearGameTextOverlay: (owner: string) => void;
}

export const useGameStore = create<GameState>((set) => ({
  revision: 0,
  mapId: null,
  agents: {},
  connectionStatus: "connecting",
  currentTime: null,
  turn: 0,
  schedulerRunning: false,
  planningError: null,
  selectedAgentId: "Jiho",
  followRequestId: 0,
  sceneContext: { kind: "world" },
  interactionNotice: null,
  gameTextOverlay: { owner: null, labels: [] },
  setSnapshot: (snapshot) =>
    set({
      revision: snapshot.revision,
      mapId: snapshot.map_id,
      currentTime: snapshot.current_time,
      turn: snapshot.turn,
      schedulerRunning: snapshot.scheduler_running,
      planningError: snapshot.planning_error,
      agents: Object.fromEntries(
        snapshot.agents.map((agent) => [agent.agent_id, agent]),
      ),
    }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  selectAgent: (selectedAgentId) =>
    set((state) => ({
      selectedAgentId,
      followRequestId: state.followRequestId + 1,
    })),
  setSceneContext: (sceneContext) => set({ sceneContext }),
  showInteractionNotice: (interactionNotice) => set({ interactionNotice }),
  dismissInteractionNotice: () => set({ interactionNotice: null }),
  setGameTextOverlay: (owner, labels) =>
    set({ gameTextOverlay: { owner, labels } }),
  clearGameTextOverlay: (owner) =>
    set((state) =>
      state.gameTextOverlay.owner === owner
        ? { gameTextOverlay: { owner: null, labels: [] } }
        : state,
    ),
}));
