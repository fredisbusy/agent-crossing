import type { TownGameHandle } from "../game";
import { DEFAULT_TICK_INTERVAL_MS, type WorldFeed } from "../net";
import { useWorldStore } from "../stores";
import { renderStateToText } from "./state-text";

/** `advanceTime`이 쓰는 고정 스텝. */
export const QA_STEP_MS = 100;

export interface QaTarget {
  game: TownGameHandle;
  feed: WorldFeed;
}

/** `window.render_game_to_text` / `window.advanceTime`을 설치하고 해제 함수를 돌려준다. */
export function installQaHooks(target: QaTarget): () => void {
  window.render_game_to_text = () => {
    const state = useWorldStore.getState();
    return renderStateToText({
      snapshot: state.snapshot,
      connection: state.connection,
      camera: target.game.getCameraState(),
      bubbleOf: (id) => target.game.getBubbleText(id),
    });
  };

  window.advanceTime = (ms) => {
    // 수동 시계에서는 도착 시각이 의미가 없으니 보간 길이를 기본값으로 고정한다(결정론).
    useWorldStore.getState().lockTickInterval(DEFAULT_TICK_INTERVAL_MS);
    target.game.freezeRealtime();
    target.feed.pause();
    let remaining = Math.max(0, ms);
    while (remaining > 0) {
      const step = Math.min(QA_STEP_MS, remaining);
      target.game.advanceClock(step);
      target.feed.advance(step);
      remaining -= step;
    }
    target.game.render();
  };

  return () => {
    delete window.render_game_to_text;
    delete window.advanceTime;
  };
}
