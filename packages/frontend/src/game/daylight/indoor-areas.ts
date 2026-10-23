import type { LocationArea } from "../../tiled";

/** 실내가 아닌 최상위 장소(광장·공원). */
const OUTDOOR_ROOTS = ["Town Square", "Johnson Park"];

/** 하위 장소가 있는 최상위 장소 중 야외가 아닌 것 = 건물. */
export function indoorAreas(areas: readonly LocationArea[]): LocationArea[] {
  return areas.filter((area) => {
    const segments = area.location_path.split(" > ");
    if (segments.length !== 2 || OUTDOOR_ROOTS.includes(segments[1])) return false;
    return areas.some((other) => other.location_path.startsWith(`${area.location_path} > `));
  });
}
