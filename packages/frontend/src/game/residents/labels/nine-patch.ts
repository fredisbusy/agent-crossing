import Phaser from "phaser";
import { PIXEL_KIT_ATLAS_KEY } from "../../map/pixel-kit";

/**
 * 말풍선 9-slice 틀 두께(그림 px). 출처: stardewrogue `public/assets/atlas.json`의
 * `ninepatch.bubble.border = 4`, `assets/sprites/town_ui.ts` (조각마다 16×16 칸, 가장자리 4px이 틀).
 */
const BUBBLE_BORDER = 4;
const CELL = 16;
/** 꼬리 `bubble_tail`: 8×6 그림이 칸 안 (0,10)부터. pivot (4,10)이 말풍선 아랫변(town_ui.ts). */
const TAIL = { sx: 0, sy: 10, w: 8, h: 6 } as const;
/** 이름표 3-patch `tag_l/m/r`: 칸 안 (0,7)부터 그림 3×9·4×9·3×9, pivot (0,7)(town_ui.ts). */
const TAG = { sy: 7, h: 9, capW: 3, midW: 4 } as const;

export const TAG_ART_HEIGHT = TAG.h;
export const TAG_CAP_WIDTH = TAG.capW;
/** 꼬리가 말풍선 몸통 아래로 더 내려오는 그림 px(윗줄은 아랫변에 겹친다). */
export const TAIL_DROP = TAIL.h - 1;

type Ctx = CanvasRenderingContext2D;

function blit(scene: Phaser.Scene, ctx: Ctx, name: string, src: [number, number, number, number], dst: [number, number, number, number]): void {
  const frame = scene.textures.getFrame(PIXEL_KIT_ATLAS_KEY, name);
  if (!frame) return;
  const image = frame.source.image as CanvasImageSource;
  ctx.drawImage(image, frame.cutX + src[0], frame.cutY + src[1], src[2], src[3], dst[0], dst[1], dst[2], dst[3]);
}

function createArtCanvas(scene: Phaser.Scene, key: string, width: number, height: number): Ctx | null {
  const texture = scene.textures.createCanvas(key, width, height);
  if (!texture) return null;
  const ctx = texture.getContext();
  ctx.imageSmoothingEnabled = false;
  return ctx;
}

function refresh(scene: Phaser.Scene, key: string): string {
  const texture = scene.textures.get(key) as Phaser.Textures.CanvasTexture;
  texture.refresh();
  texture.setFilter(Phaser.Textures.FilterMode.NEAREST);
  return key;
}

/** 이름표 몸통(3-patch)을 가운데 `midWidth`(그림 px)로 늘려 한 장으로 굽는다. 텍스처 키를 돌려준다. */
export function ensureTagTexture(scene: Phaser.Scene, midWidth: number): string | null {
  const mid = Math.max(TAG.midW, Math.round(midWidth));
  const key = `resident-tag-${mid}`;
  if (scene.textures.exists(key)) return key;
  const ctx = createArtCanvas(scene, key, TAG.capW * 2 + mid, TAG.h);
  if (!ctx) return null;
  blit(scene, ctx, "tag_l", [0, TAG.sy, TAG.capW, TAG.h], [0, 0, TAG.capW, TAG.h]);
  blit(scene, ctx, "tag_m", [0, TAG.sy, TAG.midW, TAG.h], [TAG.capW, 0, mid, TAG.h]);
  blit(scene, ctx, "tag_r", [0, TAG.sy, TAG.capW, TAG.h], [TAG.capW + mid, 0, TAG.capW, TAG.h]);
  return refresh(scene, key);
}

/**
 * 말풍선 9-slice를 `width`×`height`(그림 px, 몸통)로 늘리고 꼬리를 아랫변 가운데에 붙여 한 장으로 굽는다.
 * 캔버스 높이는 몸통 + `TAIL_DROP`. 텍스처 키를 돌려준다.
 */
export function ensureBubbleTexture(scene: Phaser.Scene, width: number, height: number): string | null {
  const w = Math.max(BUBBLE_BORDER * 2 + 2, Math.round(width));
  const h = Math.max(BUBBLE_BORDER * 2 + 2, Math.round(height));
  const key = `resident-bubble-${w}x${h}`;
  if (scene.textures.exists(key)) return key;
  const ctx = createArtCanvas(scene, key, w, h + TAIL_DROP);
  if (!ctx) return null;
  const b = BUBBLE_BORDER;
  const far = CELL - b;
  blit(scene, ctx, "bubble_tl", [0, 0, b, b], [0, 0, b, b]);
  blit(scene, ctx, "bubble_t", [0, 0, CELL, b], [b, 0, w - b * 2, b]);
  blit(scene, ctx, "bubble_tr", [far, 0, b, b], [w - b, 0, b, b]);
  blit(scene, ctx, "bubble_l", [0, 0, b, CELL], [0, b, b, h - b * 2]);
  blit(scene, ctx, "bubble_c", [0, 0, CELL, CELL], [b, b, w - b * 2, h - b * 2]);
  blit(scene, ctx, "bubble_r", [far, 0, b, CELL], [w - b, b, b, h - b * 2]);
  blit(scene, ctx, "bubble_bl", [0, far, b, b], [0, h - b, b, b]);
  blit(scene, ctx, "bubble_b", [0, far, CELL, b], [b, h - b, w - b * 2, b]);
  blit(scene, ctx, "bubble_br", [far, far, b, b], [w - b, h - b, b, b]);
  blit(scene, ctx, "bubble_tail", [TAIL.sx, TAIL.sy, TAIL.w, TAIL.h], [Math.floor((w - TAIL.w) / 2), h - 1, TAIL.w, TAIL.h]);
  return refresh(scene, key);
}

export const BUBBLE_BORDER_PX = BUBBLE_BORDER;
