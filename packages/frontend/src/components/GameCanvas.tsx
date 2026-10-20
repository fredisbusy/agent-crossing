import { useEffect, useRef } from "react";
import { createTownGame } from "../game";
import { createFeed, startWorldSession } from "../session";

/** QA 훅을 번들에 넣을지는 빌드 시점(`__QA_HOOKS__`)에 정해진다. */
function qaRequested(search: string): boolean {
  return __QA_HOOKS__ && (import.meta.env.DEV || new URLSearchParams(search).get("qa") === "1");
}

/** Phaser 장면을 담는 영역. 월드 피드도 여기서 시작한다. */
export function GameCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const search = window.location.search;
    const feed = createFeed(search);
    const game = createTownGame(container);
    const stopSession = startWorldSession(feed);

    let disposed = false;
    let uninstallQa: (() => void) | null = null;
    if (qaRequested(search)) {
      void import("../qa").then(({ installQaHooks }) => {
        if (!disposed) uninstallQa = installQaHooks({ game, feed });
      });
    }

    return () => {
      disposed = true;
      uninstallQa?.();
      stopSession();
      game.destroy();
    };
  }, []);

  return <div ref={containerRef} className="min-h-0 min-w-0 flex-1" />;
}
