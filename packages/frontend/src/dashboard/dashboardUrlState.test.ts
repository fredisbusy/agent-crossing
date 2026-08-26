import { describe, expect, it } from "vitest";
import {
  dashboardSearchParams,
  parseDashboardUrlState,
} from "./dashboardUrlState";

describe("dashboard URL state", () => {
  it("parses shareable agent and tab state", () => {
    expect(
      parseDashboardUrlState(
        "?agent=haeun&tab=relationship&target=jiho&railAgent=sujin",
      ),
    ).toEqual({
      agentId: "haeun",
      tab: "relationship",
      relationshipTargetId: "jiho",
      railAgentFilter: "sujin",
    });
  });

  it("falls back to overview for an unknown tab", () => {
    expect(parseDashboardUrlState("?tab=private-trace").tab).toBe("overview");
  });

  it("omits default values when serializing", () => {
    expect(
      dashboardSearchParams({
        agentId: "haeun",
        tab: "overview",
        relationshipTargetId: "",
        railAgentFilter: "all",
      }),
    ).toBe("?agent=haeun");
  });
});
