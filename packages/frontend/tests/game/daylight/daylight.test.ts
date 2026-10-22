import { describe, expect, it } from "vitest";
import {
  daylightAt,
  daylightForSimTime,
  isNightHour,
  multiplyColorOf,
  NIGHT_ALPHA,
  NIGHT_COLOR,
  simHourOf,
} from "../../../src/game/daylight/daylight-phase";
import { indoorAreas } from "../../../src/game/daylight/indoor-areas";

describe("simHourOf", () => {
  it("ISO 시각을 시간대 변환 없이 소수 시로 읽는다", () => {
    expect(simHourOf("2026-02-13T07:30:00.000Z")).toBe(7.5);
    expect(simHourOf("2026-02-13T23:00:00")).toBe(23);
  });
  it("읽지 못하면 null", () => {
    expect(simHourOf("nope")).toBeNull();
  });
});

describe("daylightAt", () => {
  it("낮(7~17시)은 효과가 없고 빛도 꺼져 있다", () => {
    for (const hour of [7, 12, 16.99, 17]) {
      expect(daylightAt(hour).darkness).toBeLessThan(0.02);
    }
    expect(daylightAt(12)).toMatchObject({ alpha: 0, darkness: 0 });
  });
  it("밤(19~5시)은 짙은 남색이고 빛이 최대다", () => {
    for (const hour of [19, 23, 0, 3, 5]) {
      expect(daylightAt(hour)).toEqual({ color: NIGHT_COLOR, alpha: NIGHT_ALPHA, darkness: 1 });
    }
  });
  it("저녁 18시는 주황 노을, 새벽 6시는 연한 분홍", () => {
    expect(daylightAt(18).color).toBe(0xff9a4a);
    expect(daylightAt(6).color).toBe(0xffc6d6);
  });
  it("저녁 구간에서 단조롭게 어두워지고 경계에서 끊기지 않는다", () => {
    let previous = -1;
    for (let i = 0; i <= 20; i += 1) {
      const { darkness } = daylightAt(17 + i * 0.1);
      expect(darkness).toBeGreaterThanOrEqual(previous);
      previous = darkness;
    }
    expect(Math.abs(daylightAt(16.99).alpha - daylightAt(17.01).alpha)).toBeLessThan(0.01);
  });
  it("24시간을 감싼다", () => {
    expect(daylightAt(24)).toEqual(daylightAt(0));
    expect(daylightAt(-1)).toEqual(daylightAt(23));
  });
});

describe("daylightForSimTime / multiplyColorOf", () => {
  it("sim_time이 같으면 결과가 같다(결정론)", () => {
    expect(daylightForSimTime("2026-02-13T21:00:00Z")).toEqual(daylightForSimTime("2026-02-13T21:00:00Z"));
  });
  it("낮의 곱셈 색은 흰색", () => {
    expect(multiplyColorOf(daylightForSimTime("2026-02-13T12:00:00Z"))).toBe(0xffffff);
  });
  it("읽을 수 없는 시각은 낮으로 본다", () => {
    expect(daylightForSimTime("???").alpha).toBe(0);
  });
});

describe("isNightHour", () => {
  it("19시 이후와 5시 전만 밤", () => {
    expect([4.9, 5, 12, 18.9, 19].map(isNightHour)).toEqual([true, false, false, false, true]);
  });
});

describe("indoorAreas", () => {
  const area = (location_path: string) => ({ name: location_path, location_path, x: 0, y: 0, width: 1, height: 1 });
  it("하위 장소가 있는 건물만 고르고 광장·공원은 뺀다", () => {
    const areas = [
      area("S > Cafe"),
      area("S > Cafe > Counter"),
      area("S > Johnson Park"),
      area("S > Johnson Park > Garden"),
      area("S > Town Square"),
      area("S > Hut"),
    ];
    expect(indoorAreas(areas).map((a) => a.location_path)).toEqual(["S > Cafe"]);
  });
});
