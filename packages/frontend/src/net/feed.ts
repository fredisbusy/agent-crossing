import type { WorldSnapshot } from "@agent-crossing/shared";
import type { ConnectionStatus } from "./connection";

/** 기본 틱 간격. 보간 길이도 이 값에 맞춘다. */
export const DEFAULT_TICK_INTERVAL_MS = 1000;

export interface FeedHandlers {
  onSnapshot: (snapshot: WorldSnapshot) => void;
  onStatus: (status: ConnectionStatus) => void;
}

/** WebSocket과 가짜 피드가 공유하는 인터페이스. */
export interface WorldFeed {
  start: (handlers: FeedHandlers) => void;
  stop: () => void;
  /** 실시간 진행을 멈춘다(QA `advanceTime`용). */
  pause: () => void;
  /** 멈춘 상태에서 ms만큼 진행한다. 가짜 피드만 의미가 있다. */
  advance: (ms: number) => void;
}
