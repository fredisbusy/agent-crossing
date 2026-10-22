import { TILE_SIZE } from "../../../town-layout";
import type { MapSprite } from "../objects";
import { DEFAULT_FACADE_STYLE, FACADE_STYLES, type FacadeStyle } from "./facade-style";

/** 맵 `facades` 객체 레이어 이름(scripts/maps/generate_town_map.py와 같은 값). 객체 이름 = 건물 이름. */
export const FACADE_LAYER = "facades";

/** 건물 하나의 정면(앞벽 세 줄) 그리기 계획. 좌표는 월드 px. */
export interface FacadePlan {
  name: string;
  x: number;
  y: number;
  /** 칸 수(가로). 세로는 언제나 앞벽 세 줄(48px)이다. */
  columns: number;
  /** 바깥 문이 난 칸(정면 왼쪽부터 0). */
  doorColumns: number[];
  style: FacadeStyle;
  /** 간판 가운데 x: 문을 피한 가장 긴 벽 구간의 가운데. */
  signCenterX: number;
}

/** 앞벽 줄 수(scripts/maps/town_buildings.py `FRONT_ROWS`와 같은 값). */
export const FRONT_ROWS = 3;
/** 정면 높이(앞벽 세 줄). */
export const FACADE_HEIGHT = TILE_SIZE * FRONT_ROWS;

/** 모서리 기둥 칸과 문 칸을 뺀 가장 긴 구간의 가운데 칸 위치(칸 단위, 소수 가능). */
function longestWallCenter(columns: number, doors: readonly number[]): number {
  let best = { start: 1, length: 0 };
  let start = 1;
  for (let c = 1; c <= columns - 1; c += 1) {
    const open = c < columns - 1 && !doors.includes(c);
    if (open) continue;
    if (c - start > best.length) best = { start, length: c - start };
    start = c + 1;
  }
  return best.length === 0 ? columns / 2 : best.start + best.length / 2;
}

/**
 * `facades` 객체마다 정면 계획을 만든다. `isDoor(tx, ty)`는 그 타일이 문인지(ground 레이어).
 * 문 칸은 정면 아래 줄에서 찾는다.
 */
export function planFacades(facades: readonly MapSprite[], isDoor: (tx: number, ty: number) => boolean): FacadePlan[] {
  return facades.map((facade) => {
    const columns = Math.round(facade.width / TILE_SIZE);
    const tx = Math.round(facade.x / TILE_SIZE);
    const bottomRow = Math.round((facade.y + facade.height) / TILE_SIZE) - 1;
    const doorColumns: number[] = [];
    for (let c = 0; c < columns; c += 1) if (isDoor(tx + c, bottomRow)) doorColumns.push(c);
    return {
      name: facade.frame,
      x: facade.x,
      y: facade.y,
      columns,
      doorColumns,
      style: FACADE_STYLES[facade.frame] ?? DEFAULT_FACADE_STYLE,
      signCenterX: facade.x + longestWallCenter(columns, doorColumns) * TILE_SIZE,
    };
  });
}
