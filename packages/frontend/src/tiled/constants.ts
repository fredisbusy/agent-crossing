/** 지도 상수. 주 경로(Tiled)와 대체 경로(내장 마을)가 함께 쓰므로 어느 쪽 파일에도 두지 않는다. */

/** 한 칸의 한 변(px). */
export const TILE_SIZE = 16;

export const TILESET_NAME = "town-tiles";
export const GROUND_LAYER = "ground";
export const COLLISION_LAYER = "collision";
export const LOCATIONS_LAYER = "locations";
export const LOCATION_PATH_PROPERTY = "location_path";
/** `location_path`의 단계 구분자. */
export const PATH_SEPARATOR = " > ";

/** 타일셋 gid (SPEC §15). */
export const TILE = {
  grass: 1,
  road: 2,
  floor: 3,
  wall: 4,
  water: 5,
  furniture: 6,
  door: 7,
  tree: 8,
} as const;
