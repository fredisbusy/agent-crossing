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

interface VariantSpec {
  names: readonly string[];
  weights: readonly number[];
}

/** stardewrogue `atlas.json` `variants.grass_spring` (가중치 합 100). */
const GRASS_VARIANTS: VariantSpec = {
  names: ["grass_spring_b", "grass_spring_d", "grass_spring_c", "grass_spring"],
  weights: [22, 22, 8, 48],
};
/** 실내 마루 변종(stardewrogue `town.ts`의 `FLOOR_NAMES`). */
const FLOOR_VARIANTS: VariantSpec = {
  names: ["floor_wood", "floor_wood_b", "floor_wood_c", "floor_wood_d"],
  weights: [40, 25, 20, 15],
};

/** stardewrogue `dirt_m<mask>` 자동타일 변종 수(기본 + `_v1`..`_v4`). */
const DIRT_VARIANT_COUNT = 5;
/** stardewrogue `water_m<mask>` 변종 수(기본 + `_v1`). */
const WATER_VARIANT_COUNT = 2;
const TREE_FRAMES = ["tree_town", "tree_town_b"] as const;
const BUSH_FRAMES = ["bush", "bush_b"] as const;
const FURNITURE_FRAMES = ["furn_shelf", "furn_counter", "furn_cabinet"] as const;
const SINGLE_FURNITURE = "furn_plant";
/** 마을 나무 프레임 32×48의 칸 수: 발밑 칸 위로 2칸, 좌우로 1칸을 덮는다. */
const TREE_REACH_UP = 2;
const TREE_REACH_SIDE = 1;

const MASK_N = 1;
const MASK_E = 2;
const MASK_S = 4;
const MASK_W = 8;

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

function pickWeighted(spec: VariantSpec, x: number, y: number): string {
  const h = cellHash(x, y);
  let acc = 0;
  for (let i = 0; i < spec.names.length; i += 1) {
    acc += spec.weights[i];
    if (h < acc) return spec.names[i];
  }
  return spec.names[spec.names.length - 1];
}

export function grassFrame(x: number, y: number): string {
  return pickWeighted(GRASS_VARIANTS, x, y);
}

/** 이웃 마스크 N=1, E=2, S=4, W=8. `linked`가 참인 이웃 쪽 비트가 켜진다. */
export function neighborMask(linked: (x: number, y: number) => boolean, x: number, y: number): number {
  return (
    (linked(x, y - 1) ? MASK_N : 0) |
    (linked(x + 1, y) ? MASK_E : 0) |
    (linked(x, y + 1) ? MASK_S : 0) |
    (linked(x - 1, y) ? MASK_W : 0)
  );
}

function autotileFrame(set: string, mask: number, variants: number, x: number, y: number): string {
  const v = (variantHash(x, y) >>> 16) % variants;
  return v ? `${set}_m${mask}_v${v}` : `${set}_m${mask}`;
}

export function dirtFrame(mask: number, x: number, y: number): string {
  return autotileFrame("dirt", mask, DIRT_VARIANT_COUNT, x, y);
}

/**
 * Tiled `ground` 레이어(gid 배열)를 stardewrogue 팩 프레임으로 바꾸는 계획.
 * 바닥(풀·길·마루·벽·문·물·가구)은 `ground`, 나무는 주민과 앞뒤를 맞출 `props`로 나눈다.
 */
export function planPixelKit(ground: readonly number[], width: number, height: number): PixelKitPlan {
  const at = (x: number, y: number): number | null =>
    x < 0 || y < 0 || x >= width || y >= height ? null : (ground[y * width + x] ?? null);
  const is = (x: number, y: number, ...gids: number[]): boolean => {
    const gid = at(x, y);
    return gid !== null && gids.includes(gid);
  };
  // 길은 지도 밖으로 이어진 것으로 본다(지도 끝에서 끊겨 보이지 않게).
  const isRoad = (x: number, y: number): boolean => at(x, y) === null || is(x, y, TILE.road);
  const isWallLike = (x: number, y: number): boolean => is(x, y, TILE.wall, TILE.door);
  const isOpen = (x: number, y: number): boolean => at(x, y) === null || is(x, y, TILE.grass, TILE.road, TILE.tree);
  // 큰 나무가 건물·물을 가리면 덤불(32×32)로 낮춘다.
  const treeFits = (x: number, y: number): boolean => {
    for (let dy = 1; dy <= TREE_REACH_UP; dy += 1) {
      for (let dx = -TREE_REACH_SIDE; dx <= TREE_REACH_SIDE; dx += 1) if (!isOpen(x + dx, y - dy)) return false;
    }
    return true;
  };
  // 가구 줄에서 왼쪽으로 이어진 가구 수(0이면 줄 시작).
  const furnitureRun = (x: number, y: number): number => {
    let n = 0;
    while (is(x - n - 1, y, TILE.furniture)) n += 1;
    return n;
  };

  const plan: PixelKitPlan = { ground: [], props: [] };
  const draw = (frame: string, x: number, y: number): void => {
    plan.ground.push({ frame, x: x * TILE_SIZE, y: y * TILE_SIZE });
  };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const gid = at(x, y);
      if (gid === TILE.grass || gid === TILE.road || gid === TILE.tree || gid === TILE.water) draw(grassFrame(x, y), x, y);
      if (gid === TILE.floor || gid === TILE.furniture) draw(pickWeighted(FLOOR_VARIANTS, x, y), x, y);
      if (gid === TILE.road) draw(dirtFrame(neighborMask(isRoad, x, y), x, y), x, y);
      if (gid === TILE.water) {
        const mask = neighborMask((nx, ny) => is(nx, ny, TILE.water), x, y);
        draw(autotileFrame("water", mask, WATER_VARIANT_COUNT, x, y), x, y);
      }
      if (gid === TILE.wall) draw(`wall_m${neighborMask(isWallLike, x, y)}`, x, y);
      if (gid === TILE.door) draw(isWallLike(x - 1, y) || isWallLike(x + 1, y) ? "door_h" : "door_v", x, y);
      if (gid === TILE.furniture) {
        const run = furnitureRun(x, y);
        if (run % 2 === 0) {
          const pair = is(x + 1, y, TILE.furniture);
          draw(pair ? FURNITURE_FRAMES[variantHash(x, y) % FURNITURE_FRAMES.length] : SINGLE_FURNITURE, x, y);
        }
      }
      // 벽 앞면 바로 아래 칸에 그늘 띠.
      if (gid !== null && !isWallLike(x, y) && is(x, y - 1, TILE.wall)) {
        draw("shade_wall", x, y);
      }
      if (gid === TILE.tree) {
        const frames = treeFits(x, y) ? TREE_FRAMES : BUSH_FRAMES;
        const frame = frames[variantHash(x, y) % frames.length];
        plan.props.push({ frame, x: (x + 0.5) * TILE_SIZE, y: (y + 1) * TILE_SIZE });
      }
    }
  }
  return plan;
}
