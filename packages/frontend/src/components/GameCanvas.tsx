import { useEffect, useRef } from "react";
import { createFeed, startWorldSession } from "../session";

/** QA 훅을 번들에 넣을지는 빌드 시점(`__QA_HOOKS__`)에 정해진다. */
function qaRequested(search: string): boolean {
  return __QA_HOOKS__ && (import.meta.env.DEV || new URLSearchParams(search).get("qa") === "1");
}

/**
 * Phaser 장면을 담는 영역. 월드 피드도 여기서 시작한다.
 * Phaser(약 1MB)는 첫 화면(헤더·목록)을 막지 않도록 effect 안에서 동적으로 불러온다.
 * 그래서 QA 훅(`render_game_to_text`)도 Phaser를 읽은 뒤에 설치된다: 하네스는 훅이 생길 때까지 기다려야 한다.
 */
export function GameCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const search = window.location.search;

    let disposed = false;
    let teardown: (() => void) | null = null;

    void (async () => {
      const [{ createTownGame }, feed] = await Promise.all([import("../game"), createFeed(search)]);
      // 그동안 언마운트(StrictMode 재실행 포함)됐으면 아무것도 만들지 않는다.
      if (disposed) return;
      const game = createTownGame(container);
      const stopSession = startWorldSession(feed);

      let uninstallQa: (() => void) | null = null;
      if (qaRequested(search)) {
        const { installQaHooks } = await import("../qa");
        if (!disposed) uninstallQa = installQaHooks({ game, feed });
      }
      teardown = () => {
        uninstallQa?.();
        stopSession();
        game.destroy();
      };
      // QA 훅을 기다리는 사이 언마운트됐다면 방금 만든 것을 바로 정리한다.
      if (disposed) teardown();
    })();

    return () => {
      disposed = true;
      teardown?.();
    };
  }, []);

  return <div ref={containerRef} className="min-h-0 min-w-0 flex-1" />;
}
