import { DEFAULT_MOCK_SEED, loadTownWalkGrid, MockFeed } from "../mock";
import { DEFAULT_TICK_INTERVAL_MS, WorldSocket, type WorldFeed } from "../net";
import { useWorldStore } from "../stores";

export function createFeed(search: string): WorldFeed {
  return new URLSearchParams(search).get("mock") === "1"
    ? new MockFeed(DEFAULT_MOCK_SEED, DEFAULT_TICK_INTERVAL_MS, loadTownWalkGrid)
    : new WorldSocket();
}

/** 피드를 시작해 스냅샷과 연결 상태를 스토어에 흘려 넣는다. */
export function startWorldSession(feed: WorldFeed): () => void {
  const { setSnapshot, setConnection } = useWorldStore.getState();
  feed.start({ onSnapshot: setSnapshot, onStatus: setConnection });
  return () => feed.stop();
}
