import { TILE_SIZE } from "../../../town-layout";
import { FACADE_HEIGHT, type FacadePlan } from "./facade-plan";
import { DOOR_TOP, doorGlass, facadeSeed, type GlassRect, hasWindow, WINDOW_GLASS } from "./facade-glass";
import type { FacadeStyle } from "./facade-style";

/** 그리기에 쓰는 캔버스 2D 일부(테스트에서 가짜로 바꾼다). */
export type Painter = Pick<CanvasRenderingContext2D, "fillStyle" | "fillRect">;

// 정면 세로 구역(px, 위에서부터). 처마(간판 자리) → 벽(창·문) → 주춧돌.
export const EAVE_BOTTOM = 14;
const WALL_TOP = EAVE_BOTTOM;
const FLOOR_LINE = 22;
const FOUNDATION_TOP = 44;
const COLUMN = TILE_SIZE;

const GLASS_WARM = "#f6d77a";
const GLASS_WARM_LIGHT = "#fcecb4";
const GLASS_COOL = "#9cb8cc";
const GLASS_COOL_LIGHT = "#d4e4ee";
const DOOR_WOOD = "#7a4a32";
const KNOB = "#f6d365";
const STONE = "#8f8a80";
const STONE_LIGHT = "#aaa398";
const STONE_DARK = "#6d6860";
const STEP = "#c9c2b0";
const BOX_WOOD = "#7a4a2a";
const LEAF = "#4f8a3c";
const PETALS = ["#e86a8a", "#f2c94c", "#e2533e"] as const;
const LANTERN_GLOW = "#ffd56a";
const LANTERN_CAP = "#3a2a1e";
const OUTLINE = "#3b2a20";

/** `#rrggbb`를 amount(-1..1)만큼 어둡게(음수)·밝게(양수). */
export function shade(hex: string, amount: number): string {
  const n = Number.parseInt(hex.slice(1), 16);
  const channel = (shift: number): number => {
    const v = (n >> shift) & 0xff;
    const t = amount < 0 ? v * (1 + amount) : v + (255 - v) * amount;
    return Math.max(0, Math.min(255, Math.round(t)));
  };
  return `#${((channel(16) << 16) | (channel(8) << 8) | channel(0)).toString(16).padStart(6, "0")}`;
}

function rect(ctx: Painter, color: string, x: number, y: number, w: number, h: number): void {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}

const SHINGLE_ROW = 3;

function paintRoofEdge(ctx: Painter, width: number, roof: string): void {
  const fascia = EAVE_BOTTOM - 2;
  rect(ctx, roof, 0, 0, width, fascia);
  rect(ctx, shade(roof, 0.25), 0, 0, width, 1);
  // 기와: 줄마다 아랫단 그늘과 엇갈린 이음매.
  for (let y = SHINGLE_ROW; y < fascia; y += SHINGLE_ROW) {
    rect(ctx, shade(roof, -0.18), 0, y - 1, width, 1);
    const offset = (y / SHINGLE_ROW) % 2 === 0 ? 0 : 2;
    for (let x = offset; x < width; x += 4) rect(ctx, shade(roof, -0.28), x, y - SHINGLE_ROW + 1, 1, SHINGLE_ROW - 1);
  }
  // 처마 끝 널판과 그 아래 짙은 그늘(3/4 시점 돌출감).
  rect(ctx, shade(roof, -0.45), 0, fascia, width, 2);
  rect(ctx, shade(roof, 0.15), 0, fascia, width, 1);
}

function paintMaterial(ctx: Painter, width: number, style: FacadeStyle): void {
  const height = FOUNDATION_TOP - WALL_TOP;
  rect(ctx, style.wall, 0, WALL_TOP, width, height);
  const dark = shade(style.wall, -0.22);
  const light = shade(style.wall, 0.18);
  for (let y = WALL_TOP; y < FOUNDATION_TOP; y += 1) {
    const row = y - WALL_TOP;
    if (style.material === "log" && row % 4 === 0) rect(ctx, light, 0, y, width, 1);
    if (style.material === "log" && row % 4 === 3) rect(ctx, dark, 0, y, width, 1);
    if (style.material === "plank" && row % 3 === 2) rect(ctx, dark, 0, y, width, 1);
    if (style.material === "brick" && row % 3 === 2) rect(ctx, light, 0, y, width, 1);
    if (style.material === "brick" && row % 3 !== 2) {
      for (let x = (Math.floor(row / 3) % 2) * 3; x < width; x += 6) rect(ctx, light, x, y, 1, 1);
    }
  }
  if (style.material === "plaster") {
    for (let x = 3; x < width; x += 7) rect(ctx, shade(style.wall, -0.08), x, WALL_TOP + ((x * 5) % height), 1, 1);
    for (let x = 1; x < width; x += 5) rect(ctx, shade(style.wall, 0.08), x, WALL_TOP + ((x * 7) % height), 2, 1);
    rect(ctx, style.trim, 0, FLOOR_LINE, width, 2);
  }
  // 처마 그늘 두 줄과 모서리 기둥.
  rect(ctx, shade(style.wall, -0.45), 0, WALL_TOP, width, 1);
  rect(ctx, shade(style.wall, -0.25), 0, WALL_TOP + 1, width, 1);
  rect(ctx, style.trim, 0, WALL_TOP, 2, height);
  rect(ctx, style.trim, width - 2, WALL_TOP, 2, height);
}

function paintFoundation(ctx: Painter, width: number): void {
  rect(ctx, STONE, 0, FOUNDATION_TOP, width, FACADE_HEIGHT - FOUNDATION_TOP);
  rect(ctx, STONE_DARK, 0, FOUNDATION_TOP, width, 1);
  for (let x = 0; x < width; x += 4) {
    rect(ctx, STONE_LIGHT, x + ((x / 4) % 2), FOUNDATION_TOP + 1, 3, 1);
    rect(ctx, STONE_DARK, x + 3, FOUNDATION_TOP + 1, 1, FACADE_HEIGHT - FOUNDATION_TOP - 1);
  }
  rect(ctx, shade(STONE_DARK, -0.3), 0, FACADE_HEIGHT - 1, width, 1);
}

function paintGlass(ctx: Painter, ox: number, glass: GlassRect, cool: boolean, trim: string): void {
  const { y, w, h } = glass;
  const x = ox + glass.x;
  rect(ctx, trim, x - 1, y - 1, w + 2, h + 2);
  rect(ctx, cool ? GLASS_COOL : GLASS_WARM, x, y, w, h);
  rect(ctx, cool ? GLASS_COOL_LIGHT : GLASS_WARM_LIGHT, x, y, Math.ceil(w / 2) - 1, 2);
  // 창살 십자.
  rect(ctx, trim, x + Math.floor(w / 2), y, 1, h);
  rect(ctx, trim, x, y + Math.floor(h / 2), w, 1);
}

function paintFlowerBox(ctx: Painter, x: number, y: number, w: number, seed: number): void {
  rect(ctx, BOX_WOOD, x, y + 1, w, 2);
  for (let i = 0; i < w; i += 2) {
    rect(ctx, LEAF, x + i, y, 2, 1);
    rect(ctx, PETALS[(i / 2 + seed) % PETALS.length], x + i, y - 1, 1, 1);
  }
}

function paintHouseWindow(ctx: Painter, ox: number, style: FacadeStyle, seed: number): void {
  paintGlass(ctx, ox, WINDOW_GLASS.house, false, style.trim);
  if (style.shutter) {
    for (const sx of [ox + 1, ox + 13]) {
      rect(ctx, style.shutter, sx, 27, 2, 12);
      for (let y = 28; y < 39; y += 2) rect(ctx, shade(style.shutter, -0.3), sx, y, 2, 1);
    }
  }
  if (style.flowerBox) paintFlowerBox(ctx, ox + 3, 39, 10, seed);
}



function paintShopWindow(ctx: Painter, ox: number, style: FacadeStyle): void {
  paintGlass(ctx, ox, WINDOW_GLASS.shop, false, style.trim);
  rect(ctx, style.trim, ox + 1, 41, 14, 1);
  if (!style.awning) return;
  const [a, b] = style.awning;
  for (let x = 0; x < COLUMN; x += 1) {
    const stripe = Math.floor(x / 3) % 2 === 0 ? a : b;
    rect(ctx, stripe, ox + x, 23, 1, 4);
    // 물결 아랫단: 네 칸마다 두 칸 더 내려온다.
    if (x % 4 < 2) rect(ctx, stripe, ox + x, 27, 1, 1);
  }
  rect(ctx, shade(a, -0.35), ox, 22, COLUMN, 1);
}

function paintPubWindow(ctx: Painter, ox: number, style: FacadeStyle): void {
  paintGlass(ctx, ox, WINDOW_GLASS.pub, false, style.trim);
  rect(ctx, style.trim, ox + 3, 38, 10, 1);
}

function paintCivicWindow(ctx: Painter, ox: number, style: FacadeStyle): void {
  paintGlass(ctx, ox, WINDOW_GLASS.civic, true, style.trim);
  // 아치: 위 모서리를 벽색으로 깎는다.
  rect(ctx, style.wall, ox + 3, 25, 2, 2);
  rect(ctx, style.wall, ox + 11, 25, 2, 2);
  rect(ctx, style.trim, ox + 5, 24, 6, 1);
  rect(ctx, style.trim, ox + 3, 41, 10, 1);
}

function paintLantern(ctx: Painter, x: number): void {
  rect(ctx, LANTERN_CAP, x, 25, 3, 1);
  rect(ctx, LANTERN_GLOW, x, 26, 3, 4);
  rect(ctx, LANTERN_CAP, x + 1, 30, 1, 1);
}

function paintDoor(ctx: Painter, ox: number, style: FacadeStyle): void {
  rect(ctx, style.trim, ox + 2, DOOR_TOP - 2, 12, FOUNDATION_TOP - DOOR_TOP + 2);
  rect(ctx, DOOR_WOOD, ox + 4, DOOR_TOP, 8, FOUNDATION_TOP - DOOR_TOP);
  for (let x = ox + 6; x < ox + 12; x += 3) {
    rect(ctx, shade(DOOR_WOOD, -0.25), x, DOOR_TOP, 1, FOUNDATION_TOP - DOOR_TOP);
  }
  const glass = doorGlass(style.kind);
  rect(ctx, style.kind === "civic" ? GLASS_COOL : GLASS_WARM, ox + glass.x, glass.y, glass.w, glass.h);
  rect(ctx, KNOB, ox + 10, DOOR_TOP + 10, 1, 1);
  // 문 위 작은 처마, 문 앞 디딤돌.
  rect(ctx, style.roof, ox + 1, DOOR_TOP - 5, 14, 2);
  rect(ctx, shade(style.roof, -0.35), ox + 1, DOOR_TOP - 3, 14, 1);
  rect(ctx, STEP, ox + 2, FOUNDATION_TOP, 12, FACADE_HEIGHT - FOUNDATION_TOP);
  if (style.kind === "pub") {
    paintLantern(ctx, ox);
    paintLantern(ctx, ox + 13);
  }
}

/** 정면 하나를 (0,0)부터 columns×16 × 32 px로 그린다. */
export function paintFacade(ctx: Painter, plan: FacadePlan): void {
  const width = plan.columns * COLUMN;
  const { style } = plan;
  const seed = facadeSeed(plan.name);
  paintMaterial(ctx, width, style);
  paintFoundation(ctx, width);
  for (let c = 0; c < plan.columns; c += 1) {
    if (!hasWindow(plan, c, seed)) continue;
    const ox = c * COLUMN;
    if (style.kind === "house") paintHouseWindow(ctx, ox, style, seed + c);
    if (style.kind === "shop") paintShopWindow(ctx, ox, style);
    if (style.kind === "pub") paintPubWindow(ctx, ox, style);
    if (style.kind === "civic") paintCivicWindow(ctx, ox, style);
  }
  for (const c of plan.doorColumns) paintDoor(ctx, c * COLUMN, style);
  paintRoofEdge(ctx, width, style.roof);
  // 팩 그림처럼 바깥 1px 짙은 테두리(옆선).
  rect(ctx, OUTLINE, 0, 0, 1, FACADE_HEIGHT);
  rect(ctx, OUTLINE, width - 1, 0, 1, FACADE_HEIGHT);
}
