import { LOCATION_PATH_PROPERTY, PATH_SEPARATOR } from "./constants";
import type { TileRect } from "./geometry";

export interface LocationArea {
  name: string;
  location_path: string;
  /** 월드 픽셀 좌표. */
  x: number;
  y: number;
  width: number;
  height: number;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/** 이름이 `name`인 첫 레이어. 없거나 형식이 다르면 null. */
export function findLayer(layers: unknown, name: string): Record<string, unknown> | null {
  if (!Array.isArray(layers)) return null;
  for (const layer of layers as unknown[]) {
    const record = asRecord(layer);
    if (record?.name === name) return record;
  }
  return null;
}

function readLocationPath(properties: unknown): string | null {
  if (!Array.isArray(properties)) return null;
  for (const entry of properties as unknown[]) {
    const record = asRecord(entry);
    if (record?.name === LOCATION_PATH_PROPERTY && typeof record.value === "string") return record.value;
  }
  return null;
}

/** Tiled 오브젝트 목록에서 `location_path`가 있는 사각형만 뽑는다. */
export function extractLocationAreas(objects: readonly unknown[]): LocationArea[] {
  const areas: LocationArea[] = [];
  for (const raw of objects) {
    const object = asRecord(raw);
    if (object === null) continue;
    const path = readLocationPath(object.properties);
    const { x, y, width, height } = object;
    if (path === null || typeof x !== "number" || typeof y !== "number") continue;
    if (typeof width !== "number" || typeof height !== "number") continue;
    const name = typeof object.name === "string" && object.name !== "" ? object.name : (path.split(PATH_SEPARATOR).pop() ?? path);
    areas.push({ name, location_path: path, x, y, width, height });
  }
  return areas;
}

/** 월드 픽셀 사각형을 칸 단위 사각형으로 바꾼다. */
export function toTileRect(area: LocationArea, tileWidth: number, tileHeight: number): TileRect {
  return {
    x: Math.floor(area.x / tileWidth),
    y: Math.floor(area.y / tileHeight),
    width: Math.round(area.width / tileWidth),
    height: Math.round(area.height / tileHeight),
  };
}
