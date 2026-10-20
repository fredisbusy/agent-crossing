import { TILE } from "../fallback-map";
import { TILE_SIZE } from "../../../town-layout";

/** 아틀라스 프레임 하나를 놓는 명령. `x`·`y`는 프레임 왼쪽 위 픽셀. */
export interface PixelKitDraw {
  frame: string;
  x: number;
  y: number;
}

/** 나무처럼 칸보다 크고 주민과 앞뒤가 갈리는 물체. `x`·`y`는 발밑 가운데(origin 0.5, 1). */
export interface PixelKitProp {
  frame: string;
  x: number;
  y: number;
}

export interface PixelKitPlan {
  ground: PixelKitDraw[];
  props: PixelKitProp[];
}

/** stardewrogue `atlas.json` `variants.grass_spring` (가중치 합 100). */
const GRASS_VARIANTS = {
  names: ["grass_spring_b", "grass_spring_d", "grass_spring_c", "grass_spring"],
  weights: [22, 22, 8, 48],
} as const;

/** stardewrogue `dirt_m<mask>` 자동타일 변종 수(기본 + `_v1`..`_v4`). */
const DIRT_VARIANT_COUNT = 5;
const TREE_FRAMES = ["tree_spring", "tree_spring_b"] as const;
const BUSH_FRAMES = ["bush", "bush_b"] as const;
/** 나무 프레임 64×96의 칸 수: 발밑 칸 위로 5칸, 좌우로 2칸을 덮는다. */
const TREE_REACH_UP = 5;
const TREE_REACH_SIDE = 2;

/** stardewrogue `src/gfx/autotile.ts`의 `cellHash`와 같은 값(0..99). */
export function cellHash(x: number, y: number): number {
  return (((x * 73856093) ^ (y * 19349663)) >>> 0) % 100;
}

/** stardewrogue `src/gfx/autotile.ts`의 `variantHash`와 같은 값. */
export function variantHash(x: number, y: number): number {
  let h = Math.imul((x * 73856093) ^ (y * 19349663), 0x5bd1e995) >>> 0;
  h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d) >>> 0;
  return h;
}

export function grassFrame(x: number, y: number): string {
  const h = cellHash(x, y);
  let acc = 0;
  for (let i = 0; i < GRASS_VARIANTS.names.length; i += 1) {
    acc += GRASS_VARIANTS.weights[i];
    if (h < acc) return GRASS_VARIANTS.names[i];
  }
  return GRASS_VARIANTS.names[GRASS_VARIANTS.names.length - 1];
}

/** 이웃 마스크 N=1, E=2, S=4, W=8. 지도 밖은 이어진 것으로 본다(길이 지도 끝에서 끊겨 보이지 않게). */
export function roadMask(isRoad: (x: number, y: number) => boolean, x: number, y: number): number {
  return (isRoad(x, y - 1) ? 1 : 0) | (isRoad(x + 1, y) ? 2 : 0) | (isRoad(x, y + 1) ? 4 : 0) | (isRoad(x - 1, y) ? 8 : 0);
}

export function dirtFrame(mask: number, x: number, y: number): string {
  const v = (variantHash(x, y) >>> 16) % DIRT_VARIANT_COUNT;
  return v ? `dirt_m${mask}_v${v}` : `dirt_m${mask}`;
}

/**
 * Tiled `ground` 레이어(gid 배열)에서 바깥 칸(풀·길·나무)만 팩 그림으로 바꾸는 계획.
 * 건물(바닥·벽·문·가구)과 물은 팩에 그림이 없어 계획에 넣지 않는다(기존 타일이 그대로 보인다).
 */
export function planPixelKit(ground: readonly number[], width: number, height: number): PixelKitPlan {
  const at = (x: number, y: number): number | null =>
    x < 0 || y < 0 || x >= width || y >= height ? null : (ground[y * width + x] ?? null);
  const isRoad = (x: number, y: number): boolean => {
    const gid = at(x, y);
    return gid === null || gid === TILE.road;
  };
  const isOpen = (x: number, y: number): boolean => {
    const gid = at(x, y);
    return gid === null || gid === TILE.grass || gid === TILE.road || gid === TILE.tree;
  };
  // 큰 나무가 건물·물을 가리면 덤불(32×32)로 낮춘다.
  const treeFits = (x: number, y: number): boolean => {
    for (let dy = 1; dy <= TREE_REACH_UP; dy += 1) {
      for (let dx = -TREE_REACH_SIDE; dx <= TREE_REACH_SIDE; dx += 1) if (!isOpen(x + dx, y - dy)) return false;
    }
    return true;
  };
  const plan: PixelKitPlan = { ground: [], props: [] };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const gid = at(x, y);
      if (gid !== TILE.grass && gid !== TILE.road && gid !== TILE.tree) continue;
      const px = x * TILE_SIZE;
      const py = y * TILE_SIZE;
      // 흙길 가장자리는 투명이라 풀을 먼저 깐다(stardewrogue `terrains.dirt.under`).
      plan.ground.push({ frame: grassFrame(x, y), x: px, y: py });
      if (gid === TILE.road) plan.ground.push({ frame: dirtFrame(roadMask(isRoad, x, y), x, y), x: px, y: py });
      if (gid === TILE.tree) {
        const frames = treeFits(x, y) ? TREE_FRAMES : BUSH_FRAMES;
        const frame = frames[variantHash(x, y) % frames.length];
        plan.props.push({ frame, x: px + TILE_SIZE / 2, y: py + TILE_SIZE });
      }
    }
  }
  return plan;
}
