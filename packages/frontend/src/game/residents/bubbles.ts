import type { ResidentSnapshot } from "@agent-crossing/shared";

/** 말풍선이 떠 있는 시간. */
export const BUBBLE_DURATION_MS = 4000;

interface Bubble {
  text: string;
  untilMs: number;
}

/** 스냅샷의 `utterance_text`를 몇 초 동안 말풍선으로 유지한다. */
export class BubbleTracker {
  private readonly bubbles = new Map<string, Bubble>();

  observe(residents: readonly ResidentSnapshot[], nowMs: number): void {
    for (const resident of residents) {
      if (resident.utterance_text) {
        this.bubbles.set(resident.resident_id, {
          text: resident.utterance_text,
          untilMs: nowMs + BUBBLE_DURATION_MS,
        });
      }
    }
  }

  textAt(id: string, nowMs: number): string | null {
    const bubble = this.bubbles.get(id);
    if (!bubble) return null;
    return nowMs < bubble.untilMs ? bubble.text : null;
  }
}
