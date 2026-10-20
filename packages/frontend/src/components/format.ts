import type { ConnectionStatus } from "../net";

/** ISO 8601 시뮬레이션 시각을 `YYYY-MM-DD HH:mm`으로. 파싱이 안 되면 원문. */
export function formatSimTime(iso: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return match ? `${match[1]} ${match[2]}` : iso;
}

export const CONNECTION_LABELS: Record<ConnectionStatus, string> = {
  connecting: "연결 중",
  connected: "연결됨",
  reconnecting: "재연결 중",
  mock: "가짜 피드",
};

export const CONNECTION_DOT_CLASSES: Record<ConnectionStatus, string> = {
  connecting: "bg-yellow-400",
  connected: "bg-green-400",
  reconnecting: "bg-orange-400",
  mock: "bg-sky-400",
};
