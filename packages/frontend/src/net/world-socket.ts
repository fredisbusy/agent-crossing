import type { WorldClientMessage, WorldSnapshot } from "@agent-crossing/shared";
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
  send: (data: string) => void;
  close: () => void;
}

const RESYNC_REQUEST: WorldClientMessage = { type: "resync" };

export type SocketFactory = (url: string) => SocketLike;

function browserSocket(url: string): SocketLike {
  const ws = new WebSocket(url);
  const like: SocketLike = {
    onopen: null,
    onclose: null,
    onerror: null,
    onmessage: null,
    send: (data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    },
    close: () => ws.close(),
  };
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
  /** 전체 스냅샷을 다시 요청하고 기다리는 중. 그동안 오는 delta는 버린다. */
  private awaitingResync = false;

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
    this.awaitingResync = false;
    const socket = this.createSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.handlers?.onStatus("connected");
    };
    socket.onmessage = (event) => {
      if (typeof event.data !== "string") return;
      const message = parseWorldMessage(event.data);
      if (!message) {
        this.requestResync(socket);
        return;
      }
      if (message.type === "snapshot") {
        this.lastSnapshot = message.snapshot;
        this.awaitingResync = false;
      } else {
        if (this.lastSnapshot === null) return;
        this.lastSnapshot = applyDelta(this.lastSnapshot, message);
      }
      this.handlers?.onSnapshot(this.lastSnapshot);
    };
    socket.onerror = () => {};
    socket.onclose = () => this.scheduleReconnect();
  }

  /** 메시지 하나를 놓치면 이후 delta를 합칠 기준이 어긋나므로, 기준을 버리고 전체 스냅샷을 다시 받는다. */
  private requestResync(socket: SocketLike): void {
    if (this.awaitingResync) return;
    this.awaitingResync = true;
    this.lastSnapshot = null;
    socket.send(JSON.stringify(RESYNC_REQUEST));
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
