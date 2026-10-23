import { describe, expect, it } from "vitest";
import { DEV_WORLD_SOCKET_URL, resolveWorldSocketUrl } from "../../src/net/world-socket-url";

describe("resolveWorldSocketUrl", () => {
  it("환경변수가 있으면 그대로 쓴다", () => {
    expect(resolveWorldSocketUrl("wss://api.example.com/ws/world", { protocol: "http:", hostname: "x" })).toBe(
      "wss://api.example.com/ws/world",
    );
  });

  it("빈 환경변수는 없는 것으로 본다", () => {
    expect(resolveWorldSocketUrl("  ", { protocol: "http:", hostname: "localhost" })).toBe(DEV_WORLD_SOCKET_URL);
  });

  it("http면 ws, https면 wss로 같은 호스트 8000 포트를 쓴다", () => {
    expect(resolveWorldSocketUrl(undefined, { protocol: "http:", hostname: "192.168.0.5" })).toBe("ws://192.168.0.5:8000/ws/world");
    expect(resolveWorldSocketUrl(undefined, { protocol: "https:", hostname: "town.example.com" })).toBe(
      "wss://town.example.com:8000/ws/world",
    );
  });

  it("IPv6 호스트는 대괄호로 감싼다", () => {
    expect(resolveWorldSocketUrl(undefined, { protocol: "http:", hostname: "::1" })).toBe("ws://[::1]:8000/ws/world");
  });

  it("위치가 없으면 개발 기본값이다", () => {
    expect(resolveWorldSocketUrl(undefined, undefined)).toBe(DEV_WORLD_SOCKET_URL);
  });
});
