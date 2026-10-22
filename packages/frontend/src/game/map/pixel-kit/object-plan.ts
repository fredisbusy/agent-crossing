import { TILE_SIZE } from "../../../town-layout";
import { LIGHT_OBJECT_NAME, type MapSprite } from "../objects";

/** 아틀라스 프레임 하나를 놓는 명령. `x`·`y`는 프레임 왼쪽 위 픽셀. */
export interface BakedDraw {
  frame: string;
  x: number;
  y: number;
}

/** 사각형 왼쪽 위에 origin (0,0)으로 얹는 물체. `depth`로 주민과 앞뒤를 맞춘다. */
export interface ObjectSprite {
  frame: string;
  x: number;
  y: number;
  depth: number;
  flipY: boolean;
  /** 있으면 이 애니 키(`fountain`)를 재생한다. */
  anim: string | null;
}

export interface ObjectPlan {
  baked: BakedDraw[];
  sprites: ObjectSprite[];
}

/** 막지 않아 주민이 밟고 지나가는 것: 바닥 캔버스에 굽는다. */
const BAKED_PREFIXES = ["rug_", "mat_door", "flower_bed_", "lily_pad", "reeds"] as const;
/** 분수 애니: 첫 프레임 이름 → 애니 키. */
const ANIMATED: Readonly<Record<string, string>> = { fountain_0: "fountain" };
/** 주민이 위에 눕거나 앉아 주민 뒤에 깔려야 하는 것(사각형 아래끝에서 뺄 px). */
const SEAT_DEPTH_LIFT = 1;
/**
 * 남쪽 건물(y >= 22칸)은 생성기가 세로로 뒤집어 벽이 아래쪽이다.
 * 머리 쪽이 벽을 향하는 침대는 이 줄 아래에서 flipY로 뒤집는다.
 */
const SOUTH_BUILDING_MIN_Y = 22 * TILE_SIZE;
const FLIP_IN_SOUTH: ReadonlySet<string> = new Set(["furn_bed", "furn_bed_double"]);
const FLAT_FRAMES: ReadonlySet<string> = new Set(["furn_bed", "furn_bed_double"]);

export function isBaked(frame: string): boolean {
  return BAKED_PREFIXES.some((prefix) => frame.startsWith(prefix));
}

/** 그려질 depth: 보통은 사각형 아래끝, 침대는 바닥 바로 위, 의자는 앉은 주민이 앞에 오게 조금 뒤. */
export function objectDepth(sprite: MapSprite): number {
  const bottom = sprite.y + sprite.height;
  if (FLAT_FRAMES.has(sprite.frame)) return sprite.y;
  if (sprite.frame.startsWith("furn_chair_")) return bottom - SEAT_DEPTH_LIFT;
  return bottom;
}

/** 가구·장식 객체를 바닥에 굽는 것과 따로 놓는 것으로 나눈다(`light`는 그리지 않는다). */
export function planMapObjects(furniture: readonly MapSprite[], decor: readonly MapSprite[]): ObjectPlan {
  const plan: ObjectPlan = { baked: [], sprites: [] };
  for (const sprite of [...furniture, ...decor]) {
    if (sprite.frame === LIGHT_OBJECT_NAME) continue;
    if (isBaked(sprite.frame)) {
      plan.baked.push({ frame: sprite.frame, x: sprite.x, y: sprite.y });
      continue;
    }
    plan.sprites.push({
      frame: sprite.frame,
      x: sprite.x,
      y: sprite.y,
      depth: objectDepth(sprite),
      flipY: sprite.y >= SOUTH_BUILDING_MIN_Y && FLIP_IN_SOUTH.has(sprite.frame),
      anim: ANIMATED[sprite.frame] ?? null,
    });
  }
  return plan;
}
