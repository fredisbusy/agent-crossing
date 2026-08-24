import type { SpatialAgentState, SpatialWorldSnapshot } from "@agent-crossing/shared";
import { create } from "zustand";

export type ConnectionStatus = "connecting" | "live" | "offline";

interface GameState {
  revision: number;
  mapId: string | null;
  agents: Record<string, SpatialAgentState>;
  connectionStatus: ConnectionStatus;
  setSnapshot: (snapshot: SpatialWorldSnapshot) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
}

export const useGameStore = create<GameState>((set) => ({
  revision: 0,
  mapId: null,
  agents: {},
  connectionStatus: "connecting",
  setSnapshot: (snapshot) =>
    set({
      revision: snapshot.revision,
      mapId: snapshot.map_id,
      agents: Object.fromEntries(
        snapshot.agents.map((agent) => [agent.agent_id, agent]),
      ),
    }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
}));
