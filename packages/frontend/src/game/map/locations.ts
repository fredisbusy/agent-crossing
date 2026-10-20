import { LOCATION_PATH_PROPERTY } from "./tiled-types";

export interface LocationArea {
  name: string;
  location_path: string;
  /** 월드 픽셀 좌표. */
  x: number;
  y: number;
  width: number;
  height: number;
}

interface RawObject {
  name?: unknown;
  x?: unknown;
  y?: unknown;
  width?: unknown;
  height?: unknown;
  properties?: unknown;
}

function readLocationPath(properties: unknown): string | null {
  if (!Array.isArray(properties)) return null;
  for (const entry of properties as unknown[]) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;
    if (record.name === LOCATION_PATH_PROPERTY && typeof record.value === "string") return record.value;
  }
  return null;
}

/** Tiled 오브젝트 목록에서 `location_path`가 있는 사각형만 뽑는다. */
export function extractLocationAreas(objects: readonly unknown[]): LocationArea[] {
  const areas: LocationArea[] = [];
  for (const raw of objects) {
    if (typeof raw !== "object" || raw === null) continue;
    const object = raw as RawObject;
    const path = readLocationPath(object.properties);
    if (
      path === null ||
      typeof object.x !== "number" ||
      typeof object.y !== "number" ||
      typeof object.width !== "number" ||
      typeof object.height !== "number"
    ) {
      continue;
    }
    const name = typeof object.name === "string" && object.name !== "" ? object.name : (path.split(" > ").pop() ?? path);
    areas.push({ name, location_path: path, x: object.x, y: object.y, width: object.width, height: object.height });
  }
  return areas;
}
