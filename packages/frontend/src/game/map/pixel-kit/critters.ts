import { TILE, TILE_SIZE, type LocationArea } from "../../../tiled";
import type { MapSprite } from "../objects";
import { variantHash } from "./hash";

/** 새가 앉는 곳: 공원(풀칸). 광장은 포석뿐이라 풀칸이 없다. */
const BIRD_AREA_PATH = "Smallville > Johnson Park";
const BIRD_COUNT = 4;
const BUTTERFLY_COUNT = 3;
const FLOWER_PREFIX = "flower_bed_";
/** 새 한 마리가 같은 행동을 유지하는 시간(ms)과 날갯짓·쪼기 프레임 간격. */
const BIRD_SLOT_MS = 1600;
const BIRD_FRAME_MS = 420;
/** 새가 쪼기를 고르는 확률(100분율). */
const BIRD_PECK_PERCENT = 45;
const BIRD_FLIP_PERCENT = 50;
/** 나비: 천천히 떠다니는 반경(px), 속도(rad/ms), 날갯짓 간격(ms). */
const BUTTERFLY_RADIUS_X = 14;
const BUTTERFLY_RADIUS_Y = 8;
const BUTTERFLY_SPEED = 0.0006;
const BUTTERFLY_FLAP_MS = 260;
/** 새·나비 8×8 그림이 16×16 칸 안에서 갖는 기준점(atlas.tp.json anchor). */
export const BIRD_ORIGIN = { x: 0.25, y: 1 } as const;
export const BUTTERFLY_ORIGIN = { x: 0.25, y: 0.75 } as const;
const BIRD_SEED = 0x5eed;
const BUTTERFLY_SEED = 0xf1e5;

export interface BirdPlan {
  /** 발밑 가운데 월드 px. */
  x: number;
  y: number;
  seed: number;
}

export interface ButterflyPlan {
  /** 떠다니는 중심 월드 px. */
  x: number;
  y: number;
  seed: number;
}

export interface CritterPlan {
  birds: BirdPlan[];
  butterflies: ButterflyPlan[];
}

export interface BirdPose {
  frame: string;
  flipX: boolean;
}

function hashUnit(seed: number, salt: number): number {
  return variantHash(seed ^ 0x9e37, salt) % 100;
}

/** 시각 `timeMs`의 새 모습. 같은 시드·시각이면 항상 같다. */
export function birdPose(seed: number, timeMs: number): BirdPose {
  const slot = Math.floor(timeMs / BIRD_SLOT_MS);
  const pecking = hashUnit(seed, slot) < BIRD_PECK_PERCENT;
  const step = Math.floor(timeMs / BIRD_FRAME_MS) % 2;
  return {
    frame: `${pecking ? "bird_peck" : "bird_idle"}_${step}`,
    flipX: hashUnit(seed, slot + 7919) < BIRD_FLIP_PERCENT,
  };
}

/** 시각 `timeMs`의 나비 위치(중심에서 어긋난 정도)와 날개 프레임. */
export function butterflyPose(seed: number, timeMs: number): { dx: number; dy: number; frame: string } {
  const phase = (seed % 628) / 100;
  const t = timeMs * BUTTERFLY_SPEED;
  return {
    dx: Math.cos(t + phase) * BUTTERFLY_RADIUS_X,
    dy: Math.sin(t * 1.7 + phase) * BUTTERFLY_RADIUS_Y,
    frame: `butterfly_${Math.floor(timeMs / BUTTERFLY_FLAP_MS) % 2}`,
  };
}

function inArea(area: LocationArea, cellX: number, cellY: number): boolean {
  const px = cellX * TILE_SIZE;
  const py = cellY * TILE_SIZE;
  return px >= area.x && py >= area.y && px < area.x + area.width && py < area.y + area.height;
}

function overlaps(sprite: MapSprite, cellX: number, cellY: number): boolean {
  const px = cellX * TILE_SIZE;
  const py = cellY * TILE_SIZE;
  return px >= sprite.x && py >= sprite.y && px < sprite.x + sprite.width && py < sprite.y + sprite.height;
}

/** 시드 순서로 흩어 고르되, 이미 고른 칸과 가까운 후보는 건너뛴다. */
function pickSpread<T extends { cx: number; cy: number }>(cells: readonly T[], count: number, seed: number): T[] {
  const ranked = [...cells].sort((a, b) => variantHash(a.cx, a.cy ^ seed) - variantHash(b.cx, b.cy ^ seed));
  const picked: T[] = [];
  for (const cell of ranked) {
    if (picked.length >= count) break;
    if (picked.every((p) => Math.abs(p.cx - cell.cx) + Math.abs(p.cy - cell.cy) >= 5)) picked.push(cell);
  }
  return picked;
}

/**
 * 새는 공원의 빈 풀칸에, 나비는 꽃밭 위에 둔다(칸 고르기는 시드 해시라 항상 같다).
 * `ground`는 Tiled gid 배열.
 */
export function planCritters(
  ground: readonly number[],
  width: number,
  areas: readonly LocationArea[],
  furniture: readonly MapSprite[],
  decor: readonly MapSprite[],
): CritterPlan {
  const park = areas.find((a) => a.location_path === BIRD_AREA_PATH);
  const blocked = [...furniture, ...decor];
  const grass: { cx: number; cy: number }[] = [];
  if (park) {
    for (let i = 0; i < ground.length; i += 1) {
      const cx = i % width;
      const cy = Math.floor(i / width);
      if (ground[i] === TILE.grass && inArea(park, cx, cy) && !blocked.some((b) => overlaps(b, cx, cy))) {
        grass.push({ cx, cy });
      }
    }
  }
  const birds = pickSpread(grass, BIRD_COUNT, BIRD_SEED).map(({ cx, cy }) => ({
    x: (cx + 0.5) * TILE_SIZE,
    y: (cy + 1) * TILE_SIZE - 2,
    seed: variantHash(cx, cy),
  }));
  const flowers = decor
    .filter((d) => d.frame.startsWith(FLOWER_PREFIX))
    .map((d) => ({ cx: Math.floor(d.x / TILE_SIZE), cy: Math.floor(d.y / TILE_SIZE) }));
  const butterflies = pickSpread(flowers, BUTTERFLY_COUNT, BUTTERFLY_SEED).map(({ cx, cy }) => ({
    x: (cx + 0.5) * TILE_SIZE,
    y: (cy + 0.5) * TILE_SIZE,
    seed: variantHash(cx, cy),
  }));
  return { birds, butterflies };
}
