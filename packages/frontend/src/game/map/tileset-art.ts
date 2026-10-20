import { TILE_SIZE } from "../../town-layout";
import { TILE, TILE_COUNT } from "./fallback-map";

/** 아늑한 마을 팔레트. */
export const PALETTE = {
  grass: "#8fd18a",
  grassDark: "#7bc277",
  road: "#e8cf9c",
  roadDark: "#d6b97f",
  floor: "#f3e2c0",
  floorLine: "#e2cc9f",
  wall: "#a9705a",
  wallDark: "#8a5846",
  water: "#74c2e8",
  waterLight: "#b4e3f5",
  wood: "#c28a52",
  woodDark: "#9a6a3a",
  door: "#7a4a32",
  knob: "#f6d365",
  trunk: "#7a5230",
  leaf: "#4aa564",
  leafDark: "#378a50",
} as const;

type Painter = Pick<CanvasRenderingContext2D, "fillStyle" | "fillRect">;

function rect(ctx: Painter, color: string, x: number, y: number, w: number, h: number): void {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}

const TILE_PAINTERS: Record<number, (ctx: Painter, o: number) => void> = {
  [TILE.grass]: (ctx, o) => {
    rect(ctx, PALETTE.grass, o, 0, 16, 16);
    rect(ctx, PALETTE.grassDark, o + 3, 4, 2, 1);
    rect(ctx, PALETTE.grassDark, o + 10, 11, 2, 1);
    rect(ctx, PALETTE.grassDark, o + 12, 3, 1, 2);
  },
  [TILE.road]: (ctx, o) => {
    rect(ctx, PALETTE.road, o, 0, 16, 16);
    rect(ctx, PALETTE.roadDark, o + 2, 3, 2, 2);
    rect(ctx, PALETTE.roadDark, o + 9, 9, 3, 2);
    rect(ctx, PALETTE.roadDark, o + 12, 2, 1, 1);
  },
  [TILE.floor]: (ctx, o) => {
    rect(ctx, PALETTE.floor, o, 0, 16, 16);
    rect(ctx, PALETTE.floorLine, o, 7, 16, 1);
    rect(ctx, PALETTE.floorLine, o + 7, 0, 1, 7);
    rect(ctx, PALETTE.floorLine, o + 3, 8, 1, 8);
  },
  [TILE.wall]: (ctx, o) => {
    rect(ctx, PALETTE.wall, o, 0, 16, 16);
    rect(ctx, PALETTE.wallDark, o, 5, 16, 1);
    rect(ctx, PALETTE.wallDark, o, 11, 16, 1);
    rect(ctx, PALETTE.wallDark, o + 4, 0, 1, 5);
    rect(ctx, PALETTE.wallDark, o + 11, 6, 1, 5);
  },
  [TILE.water]: (ctx, o) => {
    rect(ctx, PALETTE.water, o, 0, 16, 16);
    rect(ctx, PALETTE.waterLight, o + 2, 4, 5, 1);
    rect(ctx, PALETTE.waterLight, o + 9, 11, 5, 1);
  },
  [TILE.furniture]: (ctx, o) => {
    rect(ctx, PALETTE.floor, o, 0, 16, 16);
    rect(ctx, PALETTE.woodDark, o, 3, 16, 11);
    rect(ctx, PALETTE.wood, o, 3, 16, 8);
    rect(ctx, PALETTE.woodDark, o + 2, 6, 4, 2);
  },
  [TILE.door]: (ctx, o) => {
    rect(ctx, PALETTE.wall, o, 0, 16, 16);
    rect(ctx, PALETTE.door, o + 3, 1, 10, 15);
    rect(ctx, PALETTE.wood, o + 4, 2, 8, 14);
    rect(ctx, PALETTE.knob, o + 10, 9, 2, 2);
  },
  [TILE.tree]: (ctx, o) => {
    rect(ctx, PALETTE.grass, o, 0, 16, 16);
    rect(ctx, PALETTE.trunk, o + 7, 10, 3, 6);
    rect(ctx, PALETTE.leafDark, o + 2, 2, 12, 10);
    rect(ctx, PALETTE.leaf, o + 3, 1, 10, 9);
  },
};

/** 8타일 가로 스트립을 그린다. 타일 `gid`는 `(gid - 1) * 16` 위치. */
export function paintTileset(ctx: Painter): void {
  for (let gid = 1; gid <= TILE_COUNT; gid += 1) {
    TILE_PAINTERS[gid]?.(ctx, (gid - 1) * TILE_SIZE);
  }
}

export const TILESET_PIXEL_WIDTH = TILE_SIZE * TILE_COUNT;
export const TILESET_PIXEL_HEIGHT = TILE_SIZE;
