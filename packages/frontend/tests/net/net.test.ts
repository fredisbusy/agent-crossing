import { afterEach, describe, expect, it, vi } from "vitest";
import { parseWorldMessage } from "../../src/net/parse-message";
import { reconnectDelayMs, RECONNECT_BASE_MS, RECONNECT_MAX_MS } from "../../src/net/reconnect";
import type { WorldSnapshot } from "@agent-crossing/shared";
import { WorldSocket, type SocketLike } from "../../src/net/world-socket";

const RESIDENT = {
  resident_id: "a",
  display_name: "A",
  tile: { x: 1, y: 2 },
  location_path: "Town",
  action_description: null,
  emoji: null,
  utterance_text: "hi",
  mind_kind: "llm",
  current_plan_item: null,
};

const SNAPSHOT_JSON = JSON.stringify({
  type: "snapshot",
  snapshot: { tick: 3, sim_time: "2023-02-13T07:03:00Z", residents: [RESIDENT] },
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
    expect(message?.type).toBe("snapshot");
    if (message?.type !== "snapshot") return;
    expect(message.snapshot.tick).toBe(3);
    expect(message.snapshot.residents[0].utterance_text).toBe("hi");
    expect(message.snapshot.residents[0].current_plan_item).toBeNull();
  });

  it("parses a delta message and rejects a malformed one", () => {
    const delta = { type: "delta", tick: 4, sim_time: "2023-02-13T07:04:00Z", residents: [RESIDENT] };
    const message = parseWorldMessage(JSON.stringify(delta));
    expect(message?.type).toBe("delta");
    if (message?.type !== "delta") return;
    expect(message.tick).toBe(4);
    expect(message.residents).toHaveLength(1);
    expect(parseWorldMessage(JSON.stringify({ ...delta, residents: [{ resident_id: "a" }] }))).toBeNull();
    expect(parseWorldMessage(JSON.stringify({ type: "delta", tick: 4 }))).toBeNull();
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

describe("WorldSocket delta merge", () => {
  const delta = (tick: number, tileX: number): string =>
    JSON.stringify({
      type: "delta",
      tick,
      sim_time: "2023-02-13T07:04:00Z",
      residents: tileX < 0 ? [] : [{ ...RESIDENT, tile: { x: tileX, y: 0 } }],
    });

  function setup(): { sockets: FakeSocket[]; seen: WorldSnapshot[] } {
    const sockets: FakeSocket[] = [];
    const seen: WorldSnapshot[] = [];
    const client = new WorldSocket("ws://test", () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    });
    client.start({ onSnapshot: (s) => seen.push(s), onStatus: () => {} });
    return { sockets, seen };
  }

  it("drops a delta that arrives before any snapshot", () => {
    const { sockets, seen } = setup();
    sockets[0].onmessage?.({ data: delta(4, 9) });
    expect(seen).toHaveLength(0);
  });

  it("merges deltas into the last snapshot and passes full snapshots up", () => {
    const { sockets, seen } = setup();
    sockets[0].onmessage?.({ data: SNAPSHOT_JSON });
    sockets[0].onmessage?.({ data: delta(4, 9) });
    sockets[0].onmessage?.({ data: delta(5, -1) });
    expect(seen.map((s) => s.tick)).toEqual([3, 4, 5]);
    expect(seen[1].residents[0].tile.x).toBe(9);
    expect(seen[2].residents[0].tile.x).toBe(9);
    expect(seen[2].residents).toHaveLength(1);
  });

  it("resets the merge base on reconnect", () => {
    vi.useFakeTimers();
    const { sockets, seen } = setup();
    sockets[0].onmessage?.({ data: SNAPSHOT_JSON });
    sockets[0].onclose?.();
    vi.advanceTimersByTime(RECONNECT_BASE_MS);
    sockets[1].onmessage?.({ data: delta(6, 7) });
    expect(seen.map((s) => s.tick)).toEqual([3]);
    vi.useRealTimers();
  });
});
