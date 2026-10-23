import { rectContains, type TileRect } from "../tiled";

/**
 * 내장 대체 마을의 기하 정보 (SPEC §15).
 * town.json이 없을 때의 대체 맵과 가짜 피드(?mock=1)가 같은 도로를 공유한다.
 */

export const FALLBACK_MAP_WIDTH = 40;
export const FALLBACK_MAP_HEIGHT = 28;

export interface NamedArea {
  location_path: string;
  rect: TileRect;
}

/** 가로 큰길 (두 칸 폭). */
export const MAIN_ROAD: TileRect = { x: 2, y: 14, width: 36, height: 2 };
/** 세로 큰길 (두 칸 폭). */
export const CROSS_ROAD: TileRect = { x: 19, y: 3, width: 2, height: 22 };

export const CAFE: TileRect = { x: 6, y: 5, width: 8, height: 7 };
export const SHOP: TileRect = { x: 24, y: 18, width: 8, height: 7 };
export const POND: TileRect = { x: 30, y: 4, width: 6, height: 5 };
export const PLAZA: TileRect = { x: 17, y: 12, width: 6, height: 6 };

/** 문 타일. 도로까지 길이 이어진다. */
export const CAFE_DOOR = { x: 9, y: 11 };
export const SHOP_DOOR = { x: 27, y: 18 };

export const FALLBACK_AREAS: readonly NamedArea[] = [
  { location_path: "Town > Cafe", rect: CAFE },
  { location_path: "Town > Shop", rect: SHOP },
  { location_path: "Town > Pond", rect: POND },
  { location_path: "Town > Plaza", rect: PLAZA },
];

/** 타일이 속한 장소 경로. 어느 영역도 아니면 `Town`. */
export function locationPathAt(x: number, y: number): string {
  const area = FALLBACK_AREAS.find((candidate) => rectContains(candidate.rect, x, y));
  return area ? area.location_path : "Town";
}
