import type {
  AgentPosition,
  SpatialAgentState,
  SpatialWorldSnapshot,
  PlanItemState,
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

function parsePlanItem(value: unknown): PlanItemState | null {
  if (!isRecord(value)) {
    return null;
  }
  return typeof value.start_time === "string" &&
    typeof value.end_time === "string" &&
    typeof value.location === "string" &&
    typeof value.action_content === "string"
    ? {
        start_time: value.start_time,
        end_time: value.end_time,
        location: value.location,
        action_content: value.action_content,
      }
    : null;
}

function parseAgent(value: unknown): SpatialAgentState | null {
  if (!isRecord(value)) {
    return null;
  }
  const tilePosition = parsePosition(value.tile_position);
  const position = parsePosition(value.position);
  const destination = value.destination;
  const activeDay =
    value.active_day === null ? null : parsePlanItem(value.active_day);
  const activeHourly =
    value.active_hourly === null ? null : parsePlanItem(value.active_hourly);
  const activeMinute =
    value.active_minute === null ? null : parsePlanItem(value.active_minute);
  const dayPlan = Array.isArray(value.day_plan)
    ? value.day_plan.map(parsePlanItem)
    : null;
  const bubbleKind =
    value.bubble_kind === undefined
      ? "action"
      : ["speech", "thought", "action"].includes(String(value.bubble_kind))
        ? (value.bubble_kind as SpatialAgentState["bubble_kind"])
        : null;
  const bubbleText =
    value.bubble_text === undefined
      ? (activeMinute?.action_content ??
        (typeof value.plan === "string" ? value.plan : ""))
      : typeof value.bubble_text === "string"
        ? value.bubble_text
        : null;
  if (
    typeof value.agent_id !== "string" ||
    typeof value.name !== "string" ||
    tilePosition === null ||
    position === null ||
    (destination !== null && typeof destination !== "string") ||
    typeof value.current_action !== "string" ||
    typeof value.plan !== "string" ||
    typeof value.route_remaining !== "number" ||
    (activeDay === null && value.active_day !== null) ||
    (activeHourly === null && value.active_hourly !== null) ||
    (activeMinute === null && value.active_minute !== null) ||
    dayPlan === null ||
    dayPlan.some((item) => item === null) ||
    bubbleKind === null ||
    bubbleText === null
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
    active_day: activeDay,
    active_hourly: activeHourly,
    active_minute: activeMinute,
    day_plan: dayPlan.filter((item): item is PlanItemState => item !== null),
    bubble_kind: bubbleKind,
    bubble_text: bubbleText,
  };
}

function parseSnapshot(value: unknown): SpatialWorldSnapshot | null {
  if (
    !isRecord(value) ||
    typeof value.revision !== "number" ||
    typeof value.map_id !== "string" ||
    !Array.isArray(value.agents) ||
    (value.current_time !== null && typeof value.current_time !== "string") ||
    typeof value.turn !== "number" ||
    typeof value.scheduler_running !== "boolean"
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
    agents: agents.filter(
      (agent): agent is SpatialAgentState => agent !== null,
    ),
    current_time: value.current_time,
    turn: value.turn,
    scheduler_running: value.scheduler_running,
  };
}

function getWorldStreamUrl(): string {
  const configuredUrl = import.meta.env.VITE_WORLD_WS_URL;
  if (typeof configuredUrl === "string" && configuredUrl.length > 0) {
    return configuredUrl;
  }
  if (window.location.protocol === "https:") {
    return `wss://${window.location.host}/ws/world`;
  }
  if (import.meta.env.DEV) {
    return `ws://${window.location.hostname}:8001/ws/world`;
  }
  return `ws://${window.location.host}/ws/world`;
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
