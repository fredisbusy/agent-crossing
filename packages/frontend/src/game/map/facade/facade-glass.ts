import { TILE_SIZE } from "../../../tiled";
import type { FacadePlan } from "./facade-plan";
import type { FacadeKind } from "./facade-style";

/** 정면 안 사각형(px). 창 유리·문 유리 자리를 그리기(facade-art)와 밤 불빛(daylight)이 함께 쓴다. */
export interface GlassRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 창 유리: 칸 왼쪽 위 기준. 집은 덧문 창, 가게는 진열창, 술집은 작은 창, 학교는 높은 아치 창. */
export const WINDOW_GLASS: Readonly<Record<FacadeKind, GlassRect>> = {
  house: { x: 4, y: 28, w: 8, h: 10 },
  shop: { x: 2, y: 29, w: 12, h: 11 },
  pub: { x: 4, y: 29, w: 8, h: 8 },
  civic: { x: 4, y: 26, w: 8, h: 14 },
};

/** 문짝 위끝(px). */
export const DOOR_TOP = 25;

/** 문 유리: 가게·학교는 큰 유리, 집·술집은 작은 들창. 칸 왼쪽 위 기준. */
export function doorGlass(kind: FacadeKind): GlassRect {
  return kind === "shop" || kind === "civic"
    ? { x: 5, y: DOOR_TOP + 2, w: 6, h: 7 }
    : { x: 6, y: DOOR_TOP + 2, w: 4, h: 3 };
}

/** 건물 이름에서 뽑는 결정론적 작은 수(창 엇갈림·꽃 색). */
export function facadeSeed(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) % 997;
  return h;
}

/** 칸 c에 창을 낼지. 집·술집은 한 칸 걸러, 가게·학교는 모든 벽 칸. */
export function hasWindow(plan: FacadePlan, c: number, seed: number): boolean {
  if (c <= 0 || c >= plan.columns - 1 || plan.doorColumns.includes(c)) return false;
  if (plan.style.kind === "shop" || plan.style.kind === "civic") return true;
  return (c + seed) % 2 === 1;
}

/** 정면 하나의 창·문 유리 사각형(월드 px). 밤에 이 자리에 불을 켠다. */
export function facadeGlassRects(plan: FacadePlan): GlassRect[] {
  const seed = facadeSeed(plan.name);
  const kind = plan.style.kind;
  const rects: GlassRect[] = [];
  for (let c = 0; c < plan.columns; c += 1) {
    const glass = hasWindow(plan, c, seed) ? WINDOW_GLASS[kind] : plan.doorColumns.includes(c) ? doorGlass(kind) : null;
    if (glass) rects.push({ x: plan.x + c * TILE_SIZE + glass.x, y: plan.y + glass.y, w: glass.w, h: glass.h });
  }
  return rects;
}
