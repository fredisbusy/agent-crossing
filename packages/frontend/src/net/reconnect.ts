export const RECONNECT_BASE_MS = 500;
export const RECONNECT_MAX_MS = 15_000;

/** 지수 백오프: attempt 0 -> base, 1 -> 2*base ... 상한 max. */
export function reconnectDelayMs(
  attempt: number,
  baseMs: number = RECONNECT_BASE_MS,
  maxMs: number = RECONNECT_MAX_MS,
): number {
  const safeAttempt = Math.max(0, Math.floor(attempt));
  return Math.min(maxMs, baseMs * 2 ** safeAttempt);
}
