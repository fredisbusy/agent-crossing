import { PATH_SEPARATOR, rectContains, smallestAreaAt, type LocationArea } from "../../../tiled";

/** 한 칸의 바닥·벽 모양. 벽은 `<wall>_m<mask>` 프레임 이름의 접두사다. */
export interface PlaceStyle {
  /** 바닥 프레임 접두사(`floor_tile` → `floor_tile`, `floor_tile_b`...). */
  floor: string;
  /** 벽 자동타일 접두사(`wall`·`wall_brick`·`wall_cream`). */
  wall: string;
}

/** 간판에 붙는 건물 정보(아이콘 프레임 포함). */
export interface BuildingStyle extends PlaceStyle {
  icon: string;
}

const DEFAULT_STYLE: PlaceStyle = { floor: "floor_wood", wall: "wall" };
const BEDROOM_FLOOR = "floor_carpet";
/** 방(location_path 3단계) 중 카펫을 까는 곳. */
const CARPET_ROOMS: ReadonlySet<string> = new Set(["Bedroom", "Klaus's Room", "Maria's Room"]);
const SQUARE_PATH = "Smallville > Town Square";

const HOUSE: BuildingStyle = { floor: "floor_wood", wall: "wall", icon: "sign_icon_house" };

/** 계약 E절 `장소 → 스타일 표`(건물 이름 = location_path 2단계). */
export const BUILDING_STYLES: Readonly<Record<string, BuildingStyle>> = {
  "Hobbs Cafe": { floor: "floor_tile", wall: "wall_cream", icon: "sign_icon_cafe" },
  "The Willows Market": { floor: "floor_stone", wall: "wall_cream", icon: "sign_icon_market" },
  "Oak Hill College": { floor: "floor_study", wall: "wall_brick", icon: "sign_icon_college" },
  "The Rose and Crown Pub": { floor: "floor_dark", wall: "wall_brick", icon: "sign_icon_pub" },
  "Lin Family House": HOUSE,
  "Moore Family House": HOUSE,
  "Isabella's Apartment": HOUSE,
  "Dorm for Oak Hill College": { floor: "floor_wood", wall: "wall", icon: "sign_icon_dorm" },
  "Artist's Co-living Space": { floor: "floor_wood", wall: "wall", icon: "sign_icon_art" },
};

export function pathSegments(locationPath: string): string[] {
  return locationPath.split(PATH_SEPARATOR);
}

/** 건물 사각형이면 건물 이름, 아니면 null (`Smallville > <건물>`만 건물). */
export function buildingNameOf(area: LocationArea): string | null {
  const segments = pathSegments(area.location_path);
  return segments.length === 2 && segments[1] in BUILDING_STYLES ? segments[1] : null;
}

/** 칸 중심을 덮는 가장 작은 장소(방 > 건물 > 구역). */
export function areaAt(areas: readonly LocationArea[], px: number, py: number): LocationArea | null {
  return smallestAreaAt(areas, px, py, (area) => area);
}

/** 칸 중심 좌표(px)가 속한 장소의 바닥·벽 스타일. 어느 건물도 아니면 기본(마루·기존 벽). */
export function placeStyleAt(areas: readonly LocationArea[], px: number, py: number): PlaceStyle {
  const area = areaAt(areas, px, py);
  if (area === null) return DEFAULT_STYLE;
  const segments = pathSegments(area.location_path);
  const building = BUILDING_STYLES[segments[1] ?? ""];
  if (building === undefined) return DEFAULT_STYLE;
  const room = segments[2];
  const floor = room !== undefined && CARPET_ROOMS.has(room) ? BEDROOM_FLOOR : building.floor;
  return { floor, wall: building.wall };
}

/** 칸 중심 좌표(px)가 Town Square 사각형 안인지(흙길을 포석으로 바꾼다). */
export function isInSquare(areas: readonly LocationArea[], px: number, py: number): boolean {
  return areas.some((area) => area.location_path === SQUARE_PATH && rectContains(area, px, py));
}
