import { TILE_SIZE, type LocationArea } from "../../../tiled";
import { EAVE_BOTTOM, type FacadePlan } from "../facade";
import { BUILDING_STYLES, buildingNameOf } from "./place-style";

/** 건물 하나에 걸 간판의 위치 계획(글자 폭은 그릴 때 잰다). */
export interface SignPlan {
  label: string;
  icon: string;
  /** 간판 가운데 x. */
  centerX: number;
  /** 간판을 거는 y. `below`가 거짓이면 판자 아래끝, 참이면 판자 위끝이 여기 온다. */
  edgeY: number;
  /** 참이면 edgeY에서 아래로, 거짓이면 위로 늘어진다. 정면 간판은 처마 끝에 얹어 위로 선다. */
  below: boolean;
  /**
   * 화면 크기 고정(1/줌) 배율의 상한. 정면 간판이 멀리 볼 때 처마를 넘어 실내 앞줄을 크게 가리지 않게 막는다.
   * null이면 상한 없음.
   */
  maxScale: number | null;
  /** 간판이 넘지 않을 좌우 x(정면 양끝). 화면 고정 크기라 폭은 그릴 때 정해지므로 그때 맞춘다. null이면 제한 없음. */
  bounds: readonly [number, number] | null;
}

/**
 * 정면 간판은 처마 끝(널판 아래끝)에 판자 아래끝을 맞춘다. 벽·창·문은 가리지 않고 지붕 띠와 실내 앞줄 몇 px만 덮는다.
 * 기본 줌(지도가 화면을 덮는 1.1~1.4)에서 판자는 17~22px이라 상한(판자 24px)에 닿지 않는다.
 */
const FACADE_SIGN_MAX_SCALE = 1;

/** 판자 조각 프레임은 16×16 칸에 그림이 아래 왼쪽으로 붙어 있다(atlas.tp.json anchor). */
export const PLANK_CELL = TILE_SIZE;
export const PLANK_END_WIDTH = 4;
export const PLANK_MIDDLE_WIDTH = 8;
export const PLANK_HEIGHT = 12;
/** 판자 그림 위쪽이 프레임 위에서 떨어진 px (anchor y 0.25 × 16). */
export const PLANK_TOP_OFFSET = PLANK_CELL - PLANK_HEIGHT;
export const ICON_SIZE = 10;
/** 아이콘 그림 위쪽이 프레임 위에서 떨어진 px (anchor y 0.375 × 16). */
export const ICON_TOP_OFFSET = PLANK_CELL - ICON_SIZE;
const PADDING_X = 2;
const ICON_GAP = 2;

export interface SignLayout {
  /** 가운데 조각(8px) 반복 수. */
  middleCount: number;
  /** 판자 전체 폭. */
  width: number;
  /** 판자 왼쪽 끝 기준 아이콘 x. */
  iconX: number;
  /** 판자 왼쪽 끝 기준 글자 x. */
  textX: number;
}

/** 폭 `width`인 간판의 가운데 x를 `bounds` 안으로 옮긴다. 다 못 들어가면 bounds 가운데. */
export function clampSignCenter(centerX: number, width: number, bounds: readonly [number, number] | null): number {
  if (bounds === null) return centerX;
  const [left, right] = bounds;
  if (right - left <= width) return (left + right) / 2;
  return Math.min(Math.max(centerX, left + width / 2), right - width / 2);
}

/** 글자 폭에 맞춰 판자 폭(양끝 4 + 가운데 8의 배수)과 아이콘·글자 위치를 정한다. */
export function layoutSign(textWidth: number): SignLayout {
  const iconX = PLANK_END_WIDTH;
  const textX = iconX + ICON_SIZE + ICON_GAP;
  // 글자 오른쪽 여백까지가 오른쪽 끝 조각(4px) 앞에 들어와야 한다.
  const innerWidth = textX + Math.ceil(textWidth) + PADDING_X - PLANK_END_WIDTH;
  const middleCount = Math.max(1, Math.ceil(innerWidth / PLANK_MIDDLE_WIDTH));
  return { middleCount, width: PLANK_END_WIDTH * 2 + middleCount * PLANK_MIDDLE_WIDTH, iconX, textX };
}

/**
 * 건물마다 간판 하나. 정면이 있으면 정면 처마 아래 문을 피한 벽에, 없으면(옛 맵) 건물 위 가장자리에 건다.
 * 건물이 아닌 구역은 건너뛴다.
 */
export function planSigns(areas: readonly LocationArea[], facades: readonly FacadePlan[] = []): SignPlan[] {
  const signs: SignPlan[] = [];
  for (const area of areas) {
    const name = buildingNameOf(area);
    if (name === null) continue;
    const icon = BUILDING_STYLES[name].icon;
    const facade = facades.find((f) => f.name === name);
    signs.push(
      facade
        ? { label: name, icon, centerX: facade.signCenterX, edgeY: facade.y + EAVE_BOTTOM, below: false, maxScale: FACADE_SIGN_MAX_SCALE, bounds: [facade.x, facade.x + facade.columns * TILE_SIZE] }
        : { label: name, icon, centerX: area.x + area.width / 2, edgeY: area.y, below: false, maxScale: null, bounds: null },
    );
  }
  return signs;
}
