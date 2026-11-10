import type { WorldDelta, WorldSnapshot } from "@agent-crossing/shared";

/** 마지막 스냅샷에 delta를 합친 전체 스냅샷. 주민 순서는 유지하고 달라진 주민만 교체한다. */
export function applyDelta(base: WorldSnapshot, delta: WorldDelta): WorldSnapshot {
  const changed = new Map(delta.residents.map((resident) => [resident.resident_id, resident]));
  return {
    tick: delta.tick,
    sim_time: delta.sim_time,
    residents: base.residents.map((resident) => changed.get(resident.resident_id) ?? resident),
  };
}
