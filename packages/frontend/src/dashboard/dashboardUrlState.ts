export type DashboardTabId =
  | "overview"
  | "relationship"
  | "memory"
  | "plans"
  | "reflection"
  | "logs";

export interface DashboardUrlState {
  agentId: string;
  tab: DashboardTabId;
  relationshipTargetId: string;
  railAgentFilter: string;
}

const tabIds = new Set<DashboardTabId>([
  "overview",
  "relationship",
  "memory",
  "plans",
  "reflection",
  "logs",
]);

export function parseDashboardUrlState(search: string): DashboardUrlState {
  const params = new URLSearchParams(search);
  const requestedTab = params.get("tab") as DashboardTabId | null;
  return {
    agentId: params.get("agent") ?? "",
    tab: requestedTab && tabIds.has(requestedTab) ? requestedTab : "overview",
    relationshipTargetId: params.get("target") ?? "",
    railAgentFilter: params.get("railAgent") ?? "all",
  };
}

export function dashboardSearchParams(state: DashboardUrlState): string {
  const params = new URLSearchParams();
  if (state.agentId) params.set("agent", state.agentId);
  if (state.tab !== "overview") params.set("tab", state.tab);
  if (state.relationshipTargetId) {
    params.set("target", state.relationshipTargetId);
  }
  if (state.railAgentFilter !== "all") {
    params.set("railAgent", state.railAgentFilter);
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}
