import type { WorldSnapshot } from "@agent-crossing/shared";
import type { ConnectionStatus } from "../net";

export interface QaCamera {
  scroll_x: number;
  scroll_y: number;
  zoom: number;
}

export interface QaTextInput {
  snapshot: WorldSnapshot | null;
  connection: ConnectionStatus;
  camera: QaCamera | null;
  /** 지금 화면에 떠 있는 말풍선 텍스트. */
  bubbleOf: (residentId: string) => string | null;
}

/** 스냅샷과 화면 상태를 짧은 JSON으로 직렬화한다. 같은 입력이면 같은 문자열. */
export function renderStateToText(input: QaTextInput): string {
  const { snapshot } = input;
  return JSON.stringify({
    sim_time: snapshot?.sim_time ?? null,
    tick: snapshot?.tick ?? null,
    connection: input.connection,
    camera: input.camera,
    residents: (snapshot?.residents ?? []).map((resident) => ({
      id: resident.resident_id,
      tile: [resident.tile.x, resident.tile.y],
      action: resident.action_description,
      bubble: input.bubbleOf(resident.resident_id),
    })),
  });
}
