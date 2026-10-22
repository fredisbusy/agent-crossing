import { TILE_SIZE } from "../../../town-layout";
import type { LocationArea } from "../locations";
import { BUILDING_STYLES, buildingNameOf } from "./place-style";

/** 건물 하나에 걸 간판의 위치 계획(글자 폭은 그릴 때 잰다). */
export interface SignPlan {
  label: string;
  icon: string;
  /** 간판 가운데 x. */
  centerX: number;
  /** 간판을 거는 건물 가장자리 y. `below`가 거짓이면 판자 아래끝, 참이면 판자 위끝이 여기 온다. */
  edgeY: number;
  /** 큰길에 문이 난 남쪽 건물은 길을 지나는 주민을 가리지 않게 아래쪽(공원 쪽) 가장자리에 건다. */
  below: boolean;
}

/** 남쪽 건물 줄의 위끝(scripts/maps/generate_town_map.py `SOUTH_Y` = 22칸). 문이 큰길 쪽(위)에 있다. */
const SOUTH_ROW_Y = 22 * TILE_SIZE;

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

/** 글자 폭에 맞춰 판자 폭(양끝 4 + 가운데 8의 배수)과 아이콘·글자 위치를 정한다. */
export function layoutSign(textWidth: number): SignLayout {
  const iconX = PLANK_END_WIDTH;
  const textX = iconX + ICON_SIZE + ICON_GAP;
  // 글자 오른쪽 여백까지가 오른쪽 끝 조각(4px) 앞에 들어와야 한다.
  const innerWidth = textX + Math.ceil(textWidth) + PADDING_X - PLANK_END_WIDTH;
  const middleCount = Math.max(1, Math.ceil(innerWidth / PLANK_MIDDLE_WIDTH));
  return { middleCount, width: PLANK_END_WIDTH * 2 + middleCount * PLANK_MIDDLE_WIDTH, iconX, textX };
}

/** 건물마다 큰길 반대쪽 가장자리 가운데에 간판 하나. 건물이 아닌 구역은 건너뛴다. */
export function planSigns(areas: readonly LocationArea[]): SignPlan[] {
  const signs: SignPlan[] = [];
  for (const area of areas) {
    const name = buildingNameOf(area);
    if (name === null) continue;
    signs.push({
      label: name,
      icon: BUILDING_STYLES[name].icon,
      centerX: area.x + area.width / 2,
      edgeY: area.y >= SOUTH_ROW_Y ? area.y + area.height : area.y,
      below: area.y >= SOUTH_ROW_Y,
    });
  }
  return signs;
}
