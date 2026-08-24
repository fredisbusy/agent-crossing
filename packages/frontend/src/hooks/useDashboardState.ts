import type { DashboardState } from "@agent-crossing/shared";
import { useEffect, useState } from "react";
import { parseDashboardState } from "../dashboard/parseDashboardState";

export type DashboardConnection = "connecting" | "live" | "offline";

function dashboardStateUrl(): string {
  const configured = import.meta.env.VITE_DASHBOARD_API_URL;
  if (typeof configured === "string" && configured.length > 0) {
    return configured;
  }
  return "/dashboard/state";
}

export function useDashboardState(): {
  data: DashboardState | null;
  connection: DashboardConnection;
  error: string | null;
} {
  const [data, setData] = useState<DashboardState | null>(null);
  const [connection, setConnection] =
    useState<DashboardConnection>("connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    let inFlight: AbortController | null = null;

    async function refresh(): Promise<void> {
      inFlight?.abort();
      const controller = new AbortController();
      inFlight = controller;
      try {
        const response = await fetch(dashboardStateUrl(), {
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
          setData(parsed);
          setConnection("live");
          setError(null);
        }
      } catch (requestError) {
        if (controller.signal.aborted || stopped) return;
        setConnection("offline");
        setError(
          requestError instanceof Error
            ? requestError.message
            : "대시보드 연결 실패",
        );
      }
    }

    void refresh();
    const interval = window.setInterval(() => void refresh(), 1000);
    return () => {
      stopped = true;
      inFlight?.abort();
      window.clearInterval(interval);
    };
  }, []);

  return { data, connection, error };
}
