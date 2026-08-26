import type { DashboardEvent, PlanItemState } from "@agent-crossing/shared";

export function railEvents(
  events: DashboardEvent[],
  agentFilter: string,
): DashboardEvent[] {
  return events
    .filter((event) => agentFilter === "all" || event.agent_id === agentFilter)
    .slice()
    .reverse();
}

export function selectedAgentEvents(
  events: DashboardEvent[],
  selectedAgentId: string,
): DashboardEvent[] {
  return events
    .filter((event) => event.agent_id === selectedAgentId)
    .slice()
    .reverse();
}

export function planScheduleIssues(items: PlanItemState[]): string[] {
  const ordered = items
    .slice()
    .sort(
      (left, right) =>
        Date.parse(left.start_time) - Date.parse(right.start_time),
    );
  const issues: string[] = [];
  for (let index = 1; index < ordered.length; index += 1) {
    const previous = ordered[index - 1];
    const current = ordered[index];
    if (!previous || !current) continue;
    const previousEnd = Date.parse(previous.end_time);
    const currentStart = Date.parse(current.start_time);
    if (currentStart > previousEnd)
      issues.push(`일정 ${index}–${index + 1} 사이 공백`);
    if (currentStart < previousEnd)
      issues.push(`일정 ${index}–${index + 1} 시간이 겹침`);
  }
  return issues;
}
