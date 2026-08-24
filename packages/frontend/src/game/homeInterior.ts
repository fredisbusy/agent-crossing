import type { SpatialAgentState } from "@agent-crossing/shared";

export type HomeRoom = "bedroom" | "common" | "kitchen" | "bathroom";

export interface NormalizedHomeRoom {
  id: HomeRoom;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  residentX: number;
  residentY: number;
}

export const HOME_ROOMS: readonly NormalizedHomeRoom[] = [
  {
    id: "bedroom",
    label: "침실",
    x: 0,
    y: 0,
    width: 0.48,
    height: 0.52,
    residentX: 0.31,
    residentY: 0.35,
  },
  {
    id: "kitchen",
    label: "주방",
    x: 0.48,
    y: 0,
    width: 0.52,
    height: 0.52,
    residentX: 0.72,
    residentY: 0.34,
  },
  {
    id: "common",
    label: "거실",
    x: 0,
    y: 0.52,
    width: 0.66,
    height: 0.48,
    residentX: 0.42,
    residentY: 0.74,
  },
  {
    id: "bathroom",
    label: "욕실",
    x: 0.66,
    y: 0.52,
    width: 0.34,
    height: 0.48,
    residentX: 0.82,
    residentY: 0.76,
  },
] as const;

const ROOM_KEYWORDS: Readonly<Record<HomeRoom, readonly string[]>> = {
  bedroom: [
    "bed",
    "bedroom",
    "sleep",
    "wake",
    "dress",
    "침대",
    "침실",
    "수면",
    "잠",
    "기상",
  ],
  kitchen: [
    "kitchen",
    "cook",
    "breakfast",
    "lunch",
    "dinner",
    "meal",
    "coffee",
    "주방",
    "요리",
    "식사",
    "아침",
    "점심",
    "저녁",
  ],
  bathroom: [
    "bath",
    "shower",
    "toilet",
    "brush",
    "wash",
    "욕실",
    "샤워",
    "화장실",
    "씻",
    "양치",
  ],
  common: [
    "common",
    "living",
    "read",
    "write",
    "desk",
    "table",
    "talk",
    "relax",
    "거실",
    "공용",
    "독서",
    "대화",
    "휴식",
    "책상",
  ],
};

export function resolveHomeRoom(action: string, plan: string): HomeRoom {
  const context = `${action} ${plan}`.toLocaleLowerCase();
  for (const room of HOME_ROOMS) {
    if (ROOM_KEYWORDS[room.id].some((keyword) => context.includes(keyword))) {
      return room.id;
    }
  }
  return "common";
}

export function isAgentAtLocation(
  agent: SpatialAgentState,
  locationName: string,
): boolean {
  const destination = agent.destination?.toLocaleLowerCase() ?? "";
  const action = agent.current_action.toLocaleLowerCase();
  return (
    destination.includes(locationName.toLocaleLowerCase()) &&
    (action.startsWith("at:") || action.startsWith("arrived_at:"))
  );
}

export function homeActionLabel(agent: SpatialAgentState): string {
  const movementAction = agent.current_action.replace(/^[^:]+:/, "").trim();
  const detail = agent.plan.trim() || movementAction || "집에서 쉬는 중";
  return detail.length > 42 ? `${detail.slice(0, 39)}...` : detail;
}
