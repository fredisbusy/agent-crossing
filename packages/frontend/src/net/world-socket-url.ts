export const DEV_WORLD_SOCKET_URL = "ws://localhost:8000/ws/world";
const BACKEND_PORT = 8000;
const SOCKET_PATH = "/ws/world";

export interface SocketLocation {
  protocol: string;
  hostname: string;
}

/**
 * 월드 WebSocket 주소를 정한다. 환경변수 `VITE_WORLD_SOCKET_URL`이 있으면 그것을,
 * 없으면 현재 페이지 주소 기준(https면 wss, 같은 호스트의 8000 포트)으로 만든다.
 * 위치를 알 수 없으면 개발 기본값이다.
 */
export function resolveWorldSocketUrl(configured: string | undefined, location: SocketLocation | undefined): string {
  const trimmed = configured?.trim();
  if (trimmed) return trimmed;
  if (!location || !location.hostname) return DEV_WORLD_SOCKET_URL;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const host = location.hostname.includes(":") && !location.hostname.startsWith("[") ? `[${location.hostname}]` : location.hostname;
  return `${scheme}://${host}:${BACKEND_PORT}${SOCKET_PATH}`;
}
