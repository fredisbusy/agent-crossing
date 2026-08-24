import type { SpatialAgentState } from "@agent-crossing/shared";

export interface MainEventView {
  title: string;
  description: string;
  progressPercent: number;
  progressLabel: string;
}

function locationLeaf(location: string): string {
  return location.split(" > ").at(-1) ?? location;
}

function parseTimestamp(value: string | null): number | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

export function residentStatusLabel(
  action: string,
  connectionStatus: "connecting" | "live" | "offline",
): string {
  if (connectionStatus === "connecting") return "연결 대기";
  if (connectionStatus === "offline") return "연결 끊김";
  if (action.startsWith("moving_to:") || action.includes("moving")) {
    return "이동 중";
  }
  if (action.startsWith("planning_route")) return "경로 계산 중";
  if (action.startsWith("blocked:")) return "이동 불가";
  if (action.startsWith("idle:")) return "대기 중";
  if (action.startsWith("at:") || action.startsWith("arrived_at:")) {
    return "활동 중";
  }
  return "상태 확인 중";
}

export function residentDestinationLabel(
  agent: SpatialAgentState,
  connectionStatus: "connecting" | "live" | "offline",
): string {
  if (connectionStatus === "connecting") return "연결 대기 중";
  if (connectionStatus === "offline") return "마지막 수신 위치";
  const destination = agent.destination ?? agent.active_minute?.location;
  return destination ? locationLeaf(destination) : "목적지 없음";
}

export function residentPlanLabel(agent: SpatialAgentState): string {
  return (
    agent.active_minute?.action_content.trim() ||
    agent.bubble_text.trim() ||
    agent.plan
      .split("|")
      .find((item) => item.trim().length > 0)
      ?.trim() ||
    "계획을 불러오는 중"
  );
}

export function buildMainEventView(
  agent: SpatialAgentState,
  currentTime: string | null,
): MainEventView {
  const activeMinute = agent.active_minute;
  if (!activeMinute) {
    return {
      title: `${agent.name}의 다음 일정 준비`,
      description: residentPlanLabel(agent),
      progressPercent: 0,
      progressLabel: "일정 동기화 중",
    };
  }

  const start = parseTimestamp(activeMinute.start_time);
  const end = parseTimestamp(activeMinute.end_time);
  const now = parseTimestamp(currentTime);
  const duration = start !== null && end !== null ? end - start : 0;
  const isCurrentSchedule =
    now !== null &&
    start !== null &&
    end !== null &&
    now >= start &&
    now <= end;
  if (!isCurrentSchedule) {
    const destination = agent.destination ?? activeMinute.location;
    return {
      title: `${agent.name}의 현재 활동`,
      description: `${residentStatusLabel(agent.current_action, "live")} · ${locationLeaf(destination)}`,
      progressPercent: 0,
      progressLabel: "새 일정 동기화 중",
    };
  }
  const rawProgress = duration > 0 ? ((now - start) / duration) * 100 : 0;
  const progressPercent = Math.round(Math.min(100, Math.max(0, rawProgress)));

  return {
    title: activeMinute.action_content,
    description: `${agent.name} · ${locationLeaf(activeMinute.location)}`,
    progressPercent,
    progressLabel: `일정 진행 · ${progressPercent}%`,
  };
}
