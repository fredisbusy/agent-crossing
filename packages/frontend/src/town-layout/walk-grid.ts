import type { TilePoint, TileRect } from "./fallback-layout";

/** Tiled 맵의 `collision` 레이어와 `locations` 사각형으로 만든 통행 격자 (SPEC §15). */
export interface WalkGrid {
  width: number;
  height: number;
  /** 행 우선 배열. true면 막힌 칸(벽·물·가구·나무). */
  blocked: readonly boolean[];
  areas: readonly WalkArea[];
  /** 주민이 오갈 목적지: 하위 장소가 없는 장소마다 서는 칸 하나. */
  places: readonly WalkPlace[];
  /** 어느 장소에도 속하지 않는 칸의 이름(마을 이름). */
  outsideName: string;
}

export interface WalkArea {
  location_path: string;
  rect: TileRect;
}

export interface WalkPlace {
  location_path: string;
  tile: TilePoint;
}

const COLLISION_LAYER = "collision";
const LOCATIONS_LAYER = "locations";
const LOCATION_PATH_PROPERTY = "location_path";
const SEPARATOR = " > ";

/** 4방향 이웃. 순서를 고정해 경로가 결정론적이다. */
const NEIGHBORS: readonly TilePoint[] = [
  { x: 0, y: -1 },
  { x: 1, y: 0 },
  { x: 0, y: 1 },
  { x: -1, y: 0 },
];

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function findLayer(layers: unknown, name: string): Record<string, unknown> | null {
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

function readAreas(layer: Record<string, unknown> | null, tileWidth: number, tileHeight: number): WalkArea[] {
  const objects = layer?.objects;
  if (!Array.isArray(objects)) return [];
  const areas: WalkArea[] = [];
  for (const raw of objects as unknown[]) {
    const object = asRecord(raw);
    const path = readLocationPath(object?.properties);
    const { x, y, width, height } = object ?? {};
    if (path === null || typeof x !== "number" || typeof y !== "number") continue;
    if (typeof width !== "number" || typeof height !== "number") continue;
    areas.push({
      location_path: path,
      rect: {
        x: Math.floor(x / tileWidth),
        y: Math.floor(y / tileHeight),
        width: Math.round(width / tileWidth),
        height: Math.round(height / tileHeight),
      },
    });
  }
  return areas;
}

function contains(rect: TileRect, x: number, y: number): boolean {
  return x >= rect.x && x < rect.x + rect.width && y >= rect.y && y < rect.y + rect.height;
}

export function isWalkable(grid: WalkGrid, x: number, y: number): boolean {
  if (x < 0 || y < 0 || x >= grid.width || y >= grid.height) return false;
  return !grid.blocked[y * grid.width + x];
}

/** 칸이 속한 가장 작은 장소의 경로. 없으면 마을 이름. */
export function locationAt(grid: WalkGrid, x: number, y: number): string {
  let best: WalkArea | null = null;
  for (const area of grid.areas) {
    if (!contains(area.rect, x, y)) continue;
    if (best === null || area.rect.width * area.rect.height < best.rect.width * best.rect.height) best = area;
  }
  return best ? best.location_path : grid.outsideName;
}

/** 사각형 중심에서 가장 가까운 통행 칸(사각형 안). 동점이면 y, x가 작은 쪽. */
function standTile(grid: WalkGrid, rect: TileRect): TilePoint | null {
  const cx = rect.x + (rect.width - 1) / 2;
  const cy = rect.y + (rect.height - 1) / 2;
  let best: TilePoint | null = null;
  let bestDistance = Infinity;
  for (let y = rect.y; y < rect.y + rect.height; y += 1) {
    for (let x = rect.x; x < rect.x + rect.width; x += 1) {
      if (!isWalkable(grid, x, y)) continue;
      const distance = Math.abs(x - cx) + Math.abs(y - cy);
      if (distance < bestDistance) {
        best = { x, y };
        bestDistance = distance;
      }
    }
  }
  return best;
}

function leafAreas(areas: readonly WalkArea[]): WalkArea[] {
  return areas.filter(
    (area) => !areas.some((other) => other.location_path.startsWith(area.location_path + SEPARATOR)),
  );
}

/** Tiled JSON(파싱된 객체)에서 통행 격자를 만든다. 형식이 맞지 않으면 null. */
export function walkGridFromTiled(map: unknown): WalkGrid | null {
  const record = asRecord(map);
  if (!record) return null;
  const { width, height, tilewidth, tileheight, layers } = record;
  if (typeof width !== "number" || typeof height !== "number") return null;
  if (typeof tilewidth !== "number" || typeof tileheight !== "number") return null;
  const data = findLayer(layers, COLLISION_LAYER)?.data;
  if (!Array.isArray(data) || data.length !== width * height) return null;
  const areas = readAreas(findLayer(layers, LOCATIONS_LAYER), tilewidth, tileheight);
  const outsideName = areas[0]?.location_path.split(SEPARATOR)[0] ?? "Town";
  const grid: WalkGrid = {
    width,
    height,
    blocked: (data as unknown[]).map((value) => value !== 0),
    areas,
    places: [],
    outsideName,
  };
  const places: WalkPlace[] = [];
  for (const area of leafAreas(areas)) {
    const tile = standTile(grid, area.rect);
    if (tile) places.push({ location_path: area.location_path, tile });
  }
  return { ...grid, places };
}

/** 4방향 최단 경로(start 제외, goal 포함). 갈 수 없으면 null, 같은 칸이면 빈 배열. */
export function findPath(grid: WalkGrid, start: TilePoint, goal: TilePoint): TilePoint[] | null {
  if (!isWalkable(grid, goal.x, goal.y)) return null;
  if (start.x === goal.x && start.y === goal.y) return [];
  const key = (x: number, y: number) => y * grid.width + x;
  const previous = new Map<number, number>([[key(start.x, start.y), -1]]);
  const queue: TilePoint[] = [start];
  for (let head = 0; head < queue.length; head += 1) {
    const current = queue[head];
    for (const step of NEIGHBORS) {
      const x = current.x + step.x;
      const y = current.y + step.y;
      if (!isWalkable(grid, x, y) || previous.has(key(x, y))) continue;
      previous.set(key(x, y), key(current.x, current.y));
      if (x === goal.x && y === goal.y) return unwind(previous, key(x, y), key(start.x, start.y), grid.width);
      queue.push({ x, y });
    }
  }
  return null;
}

function unwind(previous: Map<number, number>, end: number, start: number, width: number): TilePoint[] {
  const path: TilePoint[] = [];
  for (let at = end; at !== start; at = previous.get(at) ?? start) {
    path.push({ x: at % width, y: Math.floor(at / width) });
  }
  return path.reverse();
}
