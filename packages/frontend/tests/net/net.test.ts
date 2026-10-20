import { afterEach, describe, expect, it, vi } from "vitest";
import { parseWorldMessage } from "../../src/net/parse-message";
import { reconnectDelayMs, RECONNECT_BASE_MS, RECONNECT_MAX_MS } from "../../src/net/reconnect";
import { WorldSocket, type SocketLike } from "../../src/net/world-socket";

const SNAPSHOT_JSON = JSON.stringify({
  type: "snapshot",
  snapshot: {
    tick: 3,
    sim_time: "2023-02-13T07:03:00Z",
    residents: [
      {
        resident_id: "a",
        display_name: "A",
        tile: { x: 1, y: 2 },
        location_path: "Town",
        action_description: null,
        emoji: null,
        utterance_text: "hi",
        mind_kind: "llm",
      },
    ],
  },
});

describe("reconnectDelayMs", () => {
  it("doubles each attempt and caps at the max", () => {
    expect(reconnectDelayMs(0)).toBe(RECONNECT_BASE_MS);
    expect(reconnectDelayMs(1)).toBe(RECONNECT_BASE_MS * 2);
    expect(reconnectDelayMs(2)).toBe(RECONNECT_BASE_MS * 4);
    expect(reconnectDelayMs(30)).toBe(RECONNECT_MAX_MS);
  });

  it("treats negative attempts as zero", () => {
    expect(reconnectDelayMs(-3)).toBe(RECONNECT_BASE_MS);
  });
});

describe("parseWorldMessage", () => {
  it("parses a snapshot message", () => {
    const message = parseWorldMessage(SNAPSHOT_JSON);
    expect(message?.snapshot.tick).toBe(3);
    expect(message?.snapshot.residents[0].utterance_text).toBe("hi");
  });

  it("rejects malformed input", () => {
    expect(parseWorldMessage("not json")).toBeNull();
    expect(parseWorldMessage(JSON.stringify({ type: "other" }))).toBeNull();
    expect(parseWorldMessage(JSON.stringify({ type: "snapshot", snapshot: { tick: 1 } }))).toBeNull();
  });
});

class FakeSocket implements SocketLike {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  close = vi.fn();
}

describe("WorldSocket", () => {
  afterEach(() => vi.useRealTimers());

  it("reconnects with backoff and resets after opening", () => {
    vi.useFakeTimers();
    const sockets: FakeSocket[] = [];
    const statuses: string[] = [];
    const snapshots: number[] = [];
    const client = new WorldSocket("ws://test", () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    });
    client.start({ onSnapshot: (s) => snapshots.push(s.tick), onStatus: (s) => statuses.push(s) });

    sockets[0].onclose?.();
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(RECONNECT_BASE_MS);
    expect(sockets).toHaveLength(2);

    sockets[1].onclose?.();
    vi.advanceTimersByTime(RECONNECT_BASE_MS);
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(RECONNECT_BASE_MS);
    expect(sockets).toHaveLength(3);

    sockets[2].onopen?.();
    sockets[2].onmessage?.({ data: SNAPSHOT_JSON });
    expect(snapshots).toEqual([3]);
    expect(statuses.at(-1)).toBe("connected");

    client.stop();
    sockets[2].onclose?.();
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sockets).toHaveLength(3);
  });
});
