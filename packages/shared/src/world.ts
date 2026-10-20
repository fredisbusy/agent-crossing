/**
 * 하이브리드 마을 월드 스냅샷 계약 (SPEC §9, §15).
 * 이름은 백엔드 `packages/backend/src/world/contracts.py`와 같게 유지한다.
 * 필드는 WebSocket JSON 그대로 snake_case를 쓴다.
 */

export type ResidentId = string;
/** `Town > Building > Room > Object` 형식의 위치 경로. */
export type LocationPath = string;
export type MindKind = "llm" | "schedule";

export interface TilePosition {
  x: number;
  y: number;
}

export interface ResidentSnapshot {
  resident_id: ResidentId;
  display_name: string;
  tile: TilePosition;
  location_path: LocationPath;
  action_description: string | null;
  emoji: string | null;
  utterance_text: string | null;
  /** 디버그 인스펙터 전용. */
  mind_kind: MindKind | null;
}

export interface WorldSnapshot {
  tick: number;
  /** ISO 8601 시뮬레이션 시각. */
  sim_time: string;
  residents: ResidentSnapshot[];
}

export type WorldMessage = { type: "snapshot"; snapshot: WorldSnapshot };
