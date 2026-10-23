import { DEFAULT_TICK_INTERVAL_MS, WorldSocket, type WorldFeed } from "../net";
import { useWorldStore } from "../stores";

/** `?start_hour=21`처럼 가짜 피드의 시작 시각(시)을 고른다. 낮밤 화면 확인용. */
function mockStartHour(params: URLSearchParams): number | undefined {
  const hour = Number(params.get("start_hour"));
  return params.has("start_hour") && Number.isFinite(hour) && hour >= 0 && hour < 24 ? hour : undefined;
}

/** 가짜 월드는 `?mock=1`일 때만 동적으로 불러와, 실서비스 번들에 넣지 않는다. */
export async function createFeed(search: string): Promise<WorldFeed> {
  const params = new URLSearchParams(search);
  if (params.get("mock") !== "1") return new WorldSocket();
  const { DEFAULT_MOCK_SEED, loadTownWalkGrid, MockFeed } = await import("../mock");
  return new MockFeed(DEFAULT_MOCK_SEED, DEFAULT_TICK_INTERVAL_MS, loadTownWalkGrid, mockStartHour(params), params.get("scenario") ?? undefined);
}

/** 피드를 시작해 스냅샷과 연결 상태를 스토어에 흘려 넣는다. */
export function startWorldSession(feed: WorldFeed): () => void {
  const { setSnapshot, setConnection } = useWorldStore.getState();
  feed.start({ onSnapshot: setSnapshot, onStatus: setConnection });
  return () => feed.stop();
}
