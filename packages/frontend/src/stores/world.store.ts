import { create } from "zustand";
import type { ResidentId, WorldSnapshot } from "@agent-crossing/shared";
import { DEFAULT_TICK_INTERVAL_MS, type ConnectionStatus } from "../net";
import { appendUtterances, type UtteranceHistory } from "./utterance-history";

export interface WorldState {
  snapshot: WorldSnapshot | null;
  connection: ConnectionStatus;
  selectedResidentId: ResidentId | null;
  debug: boolean;
  recentUtterances: UtteranceHistory;
  /** 스냅샷 보간 길이(ms). 네트워크 계층이 도착 간격으로 추정해 넣는다. */
  tickIntervalMs: number;
  /** QA 수동 시계에서는 추정값을 고정한다. */
  tickIntervalLocked: boolean;
  setTickInterval: (ms: number) => void;
  lockTickInterval: (ms: number) => void;
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
  tickIntervalMs: DEFAULT_TICK_INTERVAL_MS,
  tickIntervalLocked: false,
  setTickInterval: (tickIntervalMs) => set((state) => (state.tickIntervalLocked ? state : { tickIntervalMs })),
  lockTickInterval: (tickIntervalMs) => set({ tickIntervalMs, tickIntervalLocked: true }),
  setSnapshot: (snapshot) =>
    set((state) => ({ snapshot, recentUtterances: appendUtterances(state.recentUtterances, snapshot) })),
  setConnection: (connection) => set({ connection }),
  selectResident: (selectedResidentId) => set({ selectedResidentId }),
  toggleDebug: () => set((state) => ({ debug: !state.debug })),
}));
