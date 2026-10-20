import Phaser from "phaser";
import atlasImageUrl from "../../../assets/pixel-kit/atlas.png?url";
import atlasDataUrl from "../../../assets/pixel-kit/atlas.tp.json?url";
import type { PixelKitPlan } from "./cells";

export const PIXEL_KIT_ATLAS_KEY = "pixel-kit";
const PIXEL_KIT_GROUND_KEY = "pixel-kit-ground";

/** 주소에 `?art=pixel-kit`이 있을 때만 켠다(시험 단계). */
export function isPixelKitEnabled(): boolean {
  return new URLSearchParams(window.location.search).get("art") === "pixel-kit";
}

export function preloadPixelKit(scene: Phaser.Scene): void {
  scene.load.atlas(PIXEL_KIT_ATLAS_KEY, atlasImageUrl, atlasDataUrl);
}

/** 바닥은 캔버스 한 장에 구워 타일 레이어 바로 위에, 나무는 y로 주민과 앞뒤를 맞춰 따로 놓는다. */
export function drawPixelKit(scene: Phaser.Scene, plan: PixelKitPlan, widthPx: number, heightPx: number): boolean {
  if (!scene.textures.exists(PIXEL_KIT_ATLAS_KEY)) return false;
  if (!scene.textures.exists(PIXEL_KIT_GROUND_KEY)) {
    const canvas = scene.textures.createCanvas(PIXEL_KIT_GROUND_KEY, widthPx, heightPx);
    if (!canvas) return false;
    const ctx = canvas.getContext();
    for (const draw of plan.ground) {
      const frame = scene.textures.getFrame(PIXEL_KIT_ATLAS_KEY, draw.frame);
      if (!frame) continue;
      const image = frame.source.image as CanvasImageSource;
      ctx.drawImage(image, frame.cutX, frame.cutY, frame.cutWidth, frame.cutHeight, draw.x, draw.y, frame.cutWidth, frame.cutHeight);
    }
    canvas.refresh();
  }
  scene.add.image(0, 0, PIXEL_KIT_GROUND_KEY).setOrigin(0, 0).setDepth(0);
  for (const prop of plan.props) {
    scene.add.image(prop.x, prop.y, PIXEL_KIT_ATLAS_KEY, prop.frame).setOrigin(0.5, 1).setDepth(prop.y);
  }
  return true;
}
