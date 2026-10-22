import { DEFAULT_TICK_INTERVAL_MS, type FeedHandlers, type WorldFeed } from "../net";
import type { WalkGrid } from "../town-layout";
import { createMockWorld, DEFAULT_MOCK_SEED, type MockWorld } from "./mock-world";

/** 통행 격자를 비동기로 읽는 함수. null이면 내장 대체 마을을 쓴다. */
export type WalkGridLoader = () => Promise<WalkGrid | null>;

/**
 * `?mock=1` 가짜 피드. 실시간 타이머 또는 `advance(ms)`로 틱을 낸다.
 * `loadGrid`를 주면 화면과 같은 맵을 읽은 뒤 시작한다(그 전에는 틱을 내지 않는다).
 */
export class MockFeed implements WorldFeed {
  private world: MockWorld | null = null;
  private handlers: FeedHandlers | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private pendingMs = 0;

  constructor(
    private readonly seed: number = DEFAULT_MOCK_SEED,
    private readonly tickIntervalMs: number = DEFAULT_TICK_INTERVAL_MS,
    private readonly loadGrid?: WalkGridLoader,
  ) {
    if (!loadGrid) this.world = createMockWorld(seed);
  }

  start(handlers: FeedHandlers): void {
    this.handlers = handlers;
    handlers.onStatus("mock");
    if (this.world) {
      this.begin();
      return;
    }
    void this.loadGrid?.().then((grid) => {
      if (this.handlers === null) return;
      this.world = createMockWorld(this.seed, grid ?? undefined);
      this.begin();
    });
  }

  private begin(): void {
    this.emit();
    this.timer = setInterval(() => this.emit(), this.tickIntervalMs);
  }

  stop(): void {
    this.pause();
    this.handlers = null;
  }

  pause(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
  }

  advance(ms: number): void {
    this.pendingMs += ms;
    while (this.pendingMs >= this.tickIntervalMs) {
      this.pendingMs -= this.tickIntervalMs;
      this.emit();
    }
  }

  private emit(): void {
    if (this.world) this.handlers?.onSnapshot(this.world.next());
  }
}
