import type Phaser from "phaser";
import { TILE_SIZE } from "../../../town-layout";
import { paintFacade } from "./facade-art";
import { FACADE_HEIGHT, type FacadePlan } from "./facade-plan";

const TEXTURE_PREFIX = "facade:";
/** 정면 아래 길에 드리우는 그늘(바닥 캔버스 depth 0 바로 위, 주민·장식보다 아래). */
const SHADOW_HEIGHT = 3;
const SHADOW_ALPHA = 0.22;
const SHADOW_DEPTH = 1;

/**
 * 정면마다 캔버스 텍스처를 한 번 그려 앞벽 두 줄 위에 얹는다.
 * depth는 정면 아래끝: 길 위 주민은 앞에, 건물 안 주민은 뒤에 온다.
 */
export function drawFacades(scene: Phaser.Scene, plans: readonly FacadePlan[]): void {
  for (const plan of plans) {
    const key = `${TEXTURE_PREFIX}${plan.name}`;
    if (!scene.textures.exists(key)) {
      const texture = scene.textures.createCanvas(key, plan.columns * TILE_SIZE, FACADE_HEIGHT);
      if (!texture) continue;
      paintFacade(texture.getContext(), plan);
      texture.refresh();
    }
    scene.add.image(plan.x, plan.y, key).setOrigin(0, 0).setDepth(plan.y + FACADE_HEIGHT);
    scene.add
      .rectangle(plan.x, plan.y + FACADE_HEIGHT, plan.columns * TILE_SIZE, SHADOW_HEIGHT, 0x000000, SHADOW_ALPHA)
      .setOrigin(0, 0)
      .setDepth(SHADOW_DEPTH);
  }
}
