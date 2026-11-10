import type { WorldSnapshot } from "@agent-crossing/shared";
import { reconnectDelayMs } from "./reconnect";
import { applyDelta } from "./merge-delta";
import { parseWorldMessage } from "./parse-message";
import type { FeedHandlers, WorldFeed } from "./feed";
import { resolveWorldSocketUrl } from "./world-socket-url";

export interface SocketLike {
  onopen: (() => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  close: () => void;
}

export type SocketFactory = (url: string) => SocketLike;

function browserSocket(url: string): SocketLike {
  const ws = new WebSocket(url);
  const like: SocketLike = { onopen: null, onclose: null, onerror: null, onmessage: null, close: () => ws.close() };
  ws.onopen = () => like.onopen?.();
  ws.onclose = () => like.onclose?.();
  ws.onerror = () => like.onerror?.();
  ws.onmessage = (event) => like.onmessage?.({ data: event.data });
  return like;
}

/** 지수 백오프로 재연결하는 WorldMessage 클라이언트. */
export class WorldSocket implements WorldFeed {
  private socket: SocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  private stopped = true;
  private handlers: FeedHandlers | null = null;
  /** delta를 합칠 기준. 연결마다 서버가 보내는 전체 스냅샷으로 초기화한다. */
  private lastSnapshot: WorldSnapshot | null = null;

  constructor(
    private readonly url: string = resolveWorldSocketUrl(import.meta.env.VITE_WORLD_SOCKET_URL, globalThis.location),
    private readonly createSocket: SocketFactory = browserSocket,
  ) {}

  start(handlers: FeedHandlers): void {
    this.handlers = handlers;
    this.stopped = false;
    this.connect("connecting");
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
  }

  pause(): void {}

  advance(): void {}

  private connect(status: "connecting" | "reconnecting"): void {
    this.handlers?.onStatus(status);
    this.lastSnapshot = null;
    const socket = this.createSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.handlers?.onStatus("connected");
    };
    socket.onmessage = (event) => {
      if (typeof event.data !== "string") return;
      const message = parseWorldMessage(event.data);
      if (!message) return;
      if (message.type === "snapshot") {
        this.lastSnapshot = message.snapshot;
      } else {
        if (this.lastSnapshot === null) return;
        this.lastSnapshot = applyDelta(this.lastSnapshot, message);
      }
      this.handlers?.onSnapshot(this.lastSnapshot);
    };
    socket.onerror = () => {};
    socket.onclose = () => this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;
    this.socket = null;
    this.handlers?.onStatus("reconnecting");
    const delay = reconnectDelayMs(this.attempt);
    this.attempt += 1;
    this.timer = setTimeout(() => this.connect("reconnecting"), delay);
  }
}
