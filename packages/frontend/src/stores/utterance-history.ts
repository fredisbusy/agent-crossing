import type { WorldSnapshot } from "@agent-crossing/shared";

export const MAX_UTTERANCES_PER_RESIDENT = 5;

export interface UtteranceEntry {
  tick: number;
  text: string;
}

export type UtteranceHistory = Record<string, UtteranceEntry[]>;

/** 스냅샷의 새 발화를 주민별 최근 기록(최신이 앞)에 더한다. 같은 틱은 한 번만. */
export function appendUtterances(history: UtteranceHistory, snapshot: WorldSnapshot): UtteranceHistory {
  let next = history;
  for (const resident of snapshot.residents) {
    if (!resident.utterance_text) continue;
    const entries = history[resident.resident_id] ?? [];
    if (entries[0]?.tick === snapshot.tick) continue;
    const added: UtteranceEntry = { tick: snapshot.tick, text: resident.utterance_text };
    next = { ...next, [resident.resident_id]: [added, ...entries].slice(0, MAX_UTTERANCES_PER_RESIDENT) };
  }
  return next;
}
