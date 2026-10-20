import { DEFAULT_TICK_INTERVAL_MS, type FeedHandlers, type WorldFeed } from "../net";
import { createMockWorld, DEFAULT_MOCK_SEED, type MockWorld } from "./mock-world";

/** `?mock=1` 가짜 피드. 실시간 타이머 또는 `advance(ms)`로 틱을 낸다. */
export class MockFeed implements WorldFeed {
  private readonly world: MockWorld;
  private handlers: FeedHandlers | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private pendingMs = 0;

  constructor(
    seed: number = DEFAULT_MOCK_SEED,
    private readonly tickIntervalMs: number = DEFAULT_TICK_INTERVAL_MS,
  ) {
    this.world = createMockWorld(seed);
  }

  start(handlers: FeedHandlers): void {
    this.handlers = handlers;
    handlers.onStatus("mock");
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
    this.handlers?.onSnapshot(this.world.next());
  }
}
