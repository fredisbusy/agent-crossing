import type {
  SpatialAgentState,
  SpatialWorldSnapshot,
} from "@agent-crossing/shared";
import { create } from "zustand";

export type ConnectionStatus = "connecting" | "live" | "offline";
export type SceneContext =
  | { kind: "world" }
  | { kind: "interior"; name: string };

export interface WorldInteractionNotice {
  title: string;
  description: string;
}

interface GameState {
  revision: number;
  mapId: string | null;
  agents: Record<string, SpatialAgentState>;
  connectionStatus: ConnectionStatus;
  currentTime: string | null;
  turn: number;
  schedulerRunning: boolean;
  selectedAgentId: string;
  followRequestId: number;
  sceneContext: SceneContext;
  interactionNotice: WorldInteractionNotice | null;
  setSnapshot: (snapshot: SpatialWorldSnapshot) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  selectAgent: (agentId: string) => void;
  setSceneContext: (sceneContext: SceneContext) => void;
  showInteractionNotice: (notice: WorldInteractionNotice) => void;
  dismissInteractionNotice: () => void;
}

export const useGameStore = create<GameState>((set) => ({
  revision: 0,
  mapId: null,
  agents: {},
  connectionStatus: "connecting",
  currentTime: null,
  turn: 0,
  schedulerRunning: false,
  selectedAgentId: "Jiho",
  followRequestId: 0,
  sceneContext: { kind: "world" },
  interactionNotice: null,
  setSnapshot: (snapshot) =>
    set({
      revision: snapshot.revision,
      mapId: snapshot.map_id,
      currentTime: snapshot.current_time,
      turn: snapshot.turn,
      schedulerRunning: snapshot.scheduler_running,
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
}));
