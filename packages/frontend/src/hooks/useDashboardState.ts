import type {
  DashboardMemoryPage,
  DashboardState,
} from "@agent-crossing/shared";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  parseDashboardEvents,
  parseDashboardMemoryPage,
  parseDashboardState,
} from "../dashboard/parseDashboardState";

export type DashboardConnection = "connecting" | "live" | "offline";

function dashboardApiUrl(path: string): string {
  const configured = import.meta.env.VITE_DASHBOARD_API_URL;
  if (typeof configured === "string" && configured.length > 0) {
    const url = new URL(configured, window.location.origin);
    url.pathname = path;
    url.search = "";
    return url.toString();
  }
  return path;
}

export function useDashboardState(): {
  data: DashboardState | null;
  connection: DashboardConnection;
  error: string | null;
  lastUpdatedAt: Date | null;
  isStale: boolean;
  refresh: () => void;
  setAgentEnabled: (agentId: string, enabled: boolean) => Promise<void>;
  loadMemories: (
    agentId: string,
    beforeId: number | null,
    nodeType: string,
  ) => Promise<DashboardMemoryPage>;
} {
  const [data, setData] = useState<DashboardState | null>(null);
  const [connection, setConnection] =
    useState<DashboardConnection>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const refreshRef = useRef<() => void>(() => undefined);

  const refresh = useCallback(() => refreshRef.current(), []);
  const setAgentEnabled = useCallback(
    async (agentId: string, enabled: boolean): Promise<void> => {
      const response = await fetch(
        dashboardApiUrl(`/agents/${encodeURIComponent(agentId)}/activation`),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        },
      );
      if (!response.ok) {
        let detail = `활성 상태 변경 실패 (${response.status})`;
        try {
          const payload = (await response.json()) as { detail?: unknown };
          if (typeof payload.detail === "string") detail = payload.detail;
        } catch {
          // Keep the status-based fallback when the server did not return JSON.
        }
        throw new Error(detail);
      }
      refreshRef.current();
    },
    [],
  );
  const loadMemories = useCallback(
    async (
      agentId: string,
      beforeId: number | null,
      nodeType: string,
    ): Promise<DashboardMemoryPage> => {
      const url = new URL(
        dashboardApiUrl(
          `/dashboard/agents/${encodeURIComponent(agentId)}/memories`,
        ),
        window.location.origin,
      );
      url.searchParams.set("limit", "50");
      if (beforeId !== null)
        url.searchParams.set("before_id", String(beforeId));
      if (nodeType !== "all") url.searchParams.set("node_type", nodeType);
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`memory API ${response.status}`);
      const parsed = parseDashboardMemoryPage(
        (await response.json()) as unknown,
      );
      if (parsed === null)
        throw new Error("기억 목록 응답 형식이 올바르지 않습니다");
      return parsed;
    },
    [],
  );

  useEffect(() => {
    let stopped = false;
    let stateInFlight = false;
    let eventInFlight = false;
    let stateFailures = 0;
    let stateReady = false;
    let stateTimer: number | null = null;
    let eventTimer: number | null = null;
    const controllers = new Set<AbortController>();
    let latestEventSequence = 0;

    function nextStateDelay(): number {
      if (document.hidden) return 15_000;
      if (stateFailures === 0) return 3_000;
      return Math.min(30_000, 1000 * 2 ** Math.min(stateFailures - 1, 5));
    }

    function scheduleState(delay = nextStateDelay()): void {
      if (stopped) return;
      if (stateTimer !== null) window.clearTimeout(stateTimer);
      stateTimer = window.setTimeout(() => void refreshState(), delay);
    }

    function scheduleEvents(): void {
      if (stopped) return;
      if (eventTimer !== null) window.clearTimeout(eventTimer);
      eventTimer = window.setTimeout(
        () => void refreshEvents(),
        document.hidden ? 15_000 : 1_000,
      );
    }

    async function refreshState(): Promise<void> {
      if (stopped || stateInFlight) return;
      stateInFlight = true;
      const controller = new AbortController();
      controllers.add(controller);
      try {
        const stateUrl = new URL(
          dashboardApiUrl("/dashboard/state"),
          window.location.origin,
        );
        stateUrl.searchParams.set("memory_limit", "50");
        stateUrl.searchParams.set("event_limit", "0");
        const response = await fetch(stateUrl, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`dashboard API ${response.status}`);
        }
        const parsed = parseDashboardState((await response.json()) as unknown);
        if (parsed === null) {
          throw new Error("dashboard API 응답 형식이 올바르지 않습니다");
        }
        if (!stopped) {
          setData((current) => ({
            ...parsed,
            events: current?.events ?? parsed.events,
          }));
          setConnection("live");
          setError(null);
          setLastUpdatedAt(new Date());
          stateFailures = 0;
          stateReady = true;
        }
      } catch (requestError) {
        if (controller.signal.aborted || stopped) return;
        stateFailures += 1;
        setConnection("offline");
        setError(
          requestError instanceof Error
            ? requestError.message
            : "대시보드 연결 실패",
        );
      } finally {
        controllers.delete(controller);
        stateInFlight = false;
        scheduleState();
      }
    }

    async function refreshEvents(): Promise<void> {
      if (stopped || eventInFlight) return;
      eventInFlight = true;
      const controller = new AbortController();
      controllers.add(controller);
      try {
        const eventsUrl = new URL(
          dashboardApiUrl("/dashboard/events"),
          window.location.origin,
        );
        eventsUrl.searchParams.set("after", String(latestEventSequence));
        eventsUrl.searchParams.set("limit", "100");
        const response = await fetch(eventsUrl, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error(`dashboard events API ${response.status}`);
        const events = parseDashboardEvents((await response.json()) as unknown);
        if (events === null)
          throw new Error("진단 로그 응답 형식이 올바르지 않습니다");
        if (!stopped && stateReady && events.length > 0) {
          latestEventSequence = Math.max(
            latestEventSequence,
            ...events.map((event) => event.sequence),
          );
          setData((current) => {
            if (current === null) return current;
            const merged = new Map(
              [...current.events, ...events].map((event) => [
                event.sequence,
                event,
              ]),
            );
            return {
              ...current,
              events: [...merged.values()]
                .sort((left, right) => left.sequence - right.sequence)
                .slice(-100),
              latest_sequence: Math.max(
                current.latest_sequence,
                latestEventSequence,
              ),
            };
          });
        }
      } catch (requestError) {
        if (!controller.signal.aborted && !stopped) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "진단 로그 갱신 실패",
          );
        }
      } finally {
        controllers.delete(controller);
        eventInFlight = false;
        scheduleEvents();
      }
    }

    function handleVisibilityChange(): void {
      if (!document.hidden) scheduleState(0);
    }

    refreshRef.current = () => scheduleState(0);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    void refreshState();
    void refreshEvents();
    return () => {
      stopped = true;
      refreshRef.current = () => undefined;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (stateTimer !== null) window.clearTimeout(stateTimer);
      if (eventTimer !== null) window.clearTimeout(eventTimer);
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
    };
  }, []);

  return {
    data,
    connection,
    error,
    lastUpdatedAt,
    isStale: data !== null && connection === "offline",
    refresh,
    setAgentEnabled,
    loadMemories,
  };
}
