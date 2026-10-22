/** 맵 `furniture`·`decor` 객체 레이어 이름(scripts/maps/generate_town_map.py와 같은 값). */
export const FURNITURE_LAYER = "furniture";
export const DECOR_LAYER = "decor";
/** `decor` 안에서 가로등 빛 위치를 뜻하는 이름(그림 프레임이 아니다). */
export const LIGHT_OBJECT_NAME = "light";

/** 아틀라스 프레임 하나를 맵 사각형에 놓는 객체. 사각형은 월드 px이고 프레임 크기와 같다. */
export interface MapSprite {
  frame: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Tiled 객체 목록에서 이름과 사각형이 있는 것만 뽑는다.
 * 그림 타일 객체(`gid`가 있음)는 Tiled 규칙상 y가 아랫변이라 높이를 빼 윗변으로 맞춘다.
 */
export function extractMapSprites(objects: readonly unknown[]): MapSprite[] {
  const sprites: MapSprite[] = [];
  for (const raw of objects) {
    if (typeof raw !== "object" || raw === null) continue;
    const { name, x, y, width, height, gid } = raw as Record<string, unknown>;
    if (typeof name !== "string" || name === "") continue;
    if (typeof x !== "number" || typeof y !== "number" || typeof width !== "number" || typeof height !== "number") continue;
    const top = typeof gid === "number" && gid > 0 ? y - height : y;
    sprites.push({ frame: name, x, y: top, width, height });
  }
  return sprites;
}
