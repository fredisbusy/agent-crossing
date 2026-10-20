import { create } from "zustand";
import type { ResidentId, WorldSnapshot } from "@agent-crossing/shared";
import type { ConnectionStatus } from "../net";
import { appendUtterances, type UtteranceHistory } from "./utterance-history";

export interface WorldState {
  snapshot: WorldSnapshot | null;
  connection: ConnectionStatus;
  selectedResidentId: ResidentId | null;
  debug: boolean;
  recentUtterances: UtteranceHistory;
  setSnapshot: (snapshot: WorldSnapshot) => void;
  setConnection: (connection: ConnectionStatus) => void;
  selectResident: (id: ResidentId | null) => void;
  toggleDebug: () => void;
}

export const useWorldStore = create<WorldState>((set) => ({
  snapshot: null,
  connection: "connecting",
  selectedResidentId: null,
  debug: false,
  recentUtterances: {},
  setSnapshot: (snapshot) =>
    set((state) => ({ snapshot, recentUtterances: appendUtterances(state.recentUtterances, snapshot) })),
  setConnection: (connection) => set({ connection }),
  selectResident: (selectedResidentId) => set({ selectedResidentId }),
  toggleDebug: () => set((state) => ({ debug: !state.debug })),
}));
