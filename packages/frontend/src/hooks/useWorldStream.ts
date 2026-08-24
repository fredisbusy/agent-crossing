import type {
  AgentPosition,
  SpatialAgentState,
  SpatialWorldSnapshot,
} from "@agent-crossing/shared";
import { useEffect } from "react";
import { useGameStore } from "../stores/game.store";

const RECONNECT_DELAY_MS = 1500;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parsePosition(value: unknown): AgentPosition | null {
  if (!isRecord(value)) {
    return null;
  }
  return typeof value.x === "number" && typeof value.y === "number"
    ? { x: value.x, y: value.y }
    : null;
}

function parseAgent(value: unknown): SpatialAgentState | null {
  if (!isRecord(value)) {
    return null;
  }
  const tilePosition = parsePosition(value.tile_position);
  const position = parsePosition(value.position);
  const destination = value.destination;
  if (
    typeof value.agent_id !== "string" ||
    typeof value.name !== "string" ||
    tilePosition === null ||
    position === null ||
    (destination !== null && typeof destination !== "string") ||
    typeof value.current_action !== "string" ||
    typeof value.plan !== "string" ||
    typeof value.route_remaining !== "number"
  ) {
    return null;
  }
  return {
    agent_id: value.agent_id,
    name: value.name,
    tile_position: tilePosition,
    position,
    destination,
    current_action: value.current_action,
    plan: value.plan,
    route_remaining: value.route_remaining,
  };
}

function parseSnapshot(value: unknown): SpatialWorldSnapshot | null {
  if (
    !isRecord(value) ||
    typeof value.revision !== "number" ||
    typeof value.map_id !== "string" ||
    !Array.isArray(value.agents)
  ) {
    return null;
  }
  const agents = value.agents.map(parseAgent);
  if (agents.some((agent) => agent === null)) {
    return null;
  }
  return {
    revision: value.revision,
    map_id: value.map_id,
    agents: agents.filter((agent): agent is SpatialAgentState => agent !== null),
  };
}

function getWorldStreamUrl(): string {
  const configuredUrl = import.meta.env.VITE_WORLD_WS_URL;
  if (typeof configuredUrl === "string" && configuredUrl.length > 0) {
    return configuredUrl;
  }
  if (import.meta.env.DEV) {
    return `ws://${window.location.hostname}:8000/ws/world`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/world`;
}

export function useWorldStream(): void {
  const setSnapshot = useGameStore((state) => state.setSnapshot);
  const setConnectionStatus = useGameStore(
    (state) => state.setConnectionStatus,
  );

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let stopped = false;

    const connect = () => {
      setConnectionStatus("connecting");
      const connectedSocket = new WebSocket(getWorldStreamUrl());
      socket = connectedSocket;
      connectedSocket.addEventListener("open", () => {
        if (socket === connectedSocket) {
          setConnectionStatus("live");
        }
      });
      connectedSocket.addEventListener(
        "message",
        (event: MessageEvent<unknown>) => {
          if (socket !== connectedSocket || typeof event.data !== "string") {
            return;
          }
          try {
            const snapshot = parseSnapshot(JSON.parse(event.data) as unknown);
            if (snapshot !== null) {
              setSnapshot(snapshot);
            }
          } catch {
            // Ignore malformed frames and wait for the next authoritative snapshot.
          }
        },
      );
      connectedSocket.addEventListener("close", () => {
        if (socket !== connectedSocket) {
          return;
        }
        socket = null;
        setConnectionStatus("offline");
        if (!stopped) {
          reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
        }
      });
      connectedSocket.addEventListener("error", () => connectedSocket.close());
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      const activeSocket = socket;
      socket = null;
      activeSocket?.close();
    };
  }, [setConnectionStatus, setSnapshot]);
}
