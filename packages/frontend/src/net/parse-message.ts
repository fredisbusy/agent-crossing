import type { ResidentSnapshot, WorldMessage, WorldSnapshot } from "@agent-crossing/shared";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isResident(value: unknown): value is ResidentSnapshot {
  if (!isRecord(value) || !isRecord(value.tile)) return false;
  return (
    typeof value.resident_id === "string" &&
    typeof value.display_name === "string" &&
    typeof value.tile.x === "number" &&
    typeof value.tile.y === "number" &&
    typeof value.location_path === "string" &&
    isNullableString(value.action_description) &&
    isNullableString(value.emoji) &&
    isNullableString(value.utterance_text) &&
    isNullableString(value.mind_kind) &&
    isNullableString(value.current_plan_item)
  );
}

function isSnapshot(value: unknown): value is WorldSnapshot {
  return (
    isRecord(value) &&
    typeof value.tick === "number" &&
    typeof value.sim_time === "string" &&
    Array.isArray(value.residents) &&
    value.residents.every(isResident)
  );
}

/** WebSocket 원문을 `WorldMessage`로. 형식이 다르면 null. */
export function parseWorldMessage(raw: string): WorldMessage | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (isRecord(parsed) && parsed.type === "snapshot" && isSnapshot(parsed.snapshot)) {
    return { type: "snapshot", snapshot: parsed.snapshot };
  }
  return null;
}
