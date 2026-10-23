import Phaser from "phaser";
import atlasImageUrl from "../../../assets/pixel-kit/atlas.png?url";
import atlasDataUrl from "../../../assets/pixel-kit/atlas.tp.json?url";
import type { PixelKitPlan } from "./cells";
import { PIXEL_KIT_ATLAS_KEY } from "./atlas-key";
import { drawPixelKitObjects, type SignRect } from "./object-layer";

const PIXEL_KIT_GROUND_KEY = "pixel-kit-ground";
const OUTSIDE_GRASS_FRAME = "grass_spring_b";
const OUTSIDE_TINT = 0xb8c8b0;
const OUTSIDE_DEPTH = -1;

/** 픽셀 팩이 기본 화풍이다. 아틀라스를 못 읽었을 때만 코드로 그린 타일·원형 주민으로 대체한다. */
export function hasPixelKit(scene: Phaser.Scene): boolean {
  return scene.textures.exists(PIXEL_KIT_ATLAS_KEY);
}

export function preloadPixelKit(scene: Phaser.Scene): void {
  scene.load.atlas(PIXEL_KIT_ATLAS_KEY, atlasImageUrl, atlasDataUrl);
}

/**
 * 바닥·깔개는 캔버스 한 장에 구워 타일 레이어 바로 위에, 나무·가구·장식·간판·생물은 y로 주민과 앞뒤를 맞춰 따로 놓는다.
 * 그렸으면 간판 사각형을 돌려주는 함수를, 아틀라스가 없으면 null을 돌려준다.
 */
export function drawPixelKit(scene: Phaser.Scene, plan: PixelKitPlan, widthPx: number, heightPx: number): (() => SignRect[]) | null {
  if (!scene.textures.exists(PIXEL_KIT_ATLAS_KEY)) return null;
  if (!scene.textures.exists(PIXEL_KIT_GROUND_KEY)) {
    const canvas = scene.textures.createCanvas(PIXEL_KIT_GROUND_KEY, widthPx, heightPx);
    if (!canvas) return null;
    const ctx = canvas.getContext();
    for (const draw of plan.ground) {
      const frame = scene.textures.getFrame(PIXEL_KIT_ATLAS_KEY, draw.frame);
      if (!frame) continue;
      const image = frame.source.image as CanvasImageSource;
      ctx.drawImage(image, frame.cutX, frame.cutY, frame.cutWidth, frame.cutHeight, draw.x, draw.y, frame.cutWidth, frame.cutHeight);
    }
    canvas.refresh();
  }
  // 지도보다 넓은 화면에서 생기는 위아래 띠: 같은 풀을 지도 둘레에 깔고 조금 어둡게 해 지도 밖임을 드러낸다.
  scene.add
    .tileSprite(-widthPx, -heightPx, widthPx * 3, heightPx * 3, PIXEL_KIT_ATLAS_KEY, OUTSIDE_GRASS_FRAME)
    .setOrigin(0, 0)
    .setDepth(OUTSIDE_DEPTH)
    .setTint(OUTSIDE_TINT);
  scene.add.image(0, 0, PIXEL_KIT_GROUND_KEY).setOrigin(0, 0).setDepth(0);
  for (const prop of plan.props) {
    scene.add.image(prop.x, prop.y, PIXEL_KIT_ATLAS_KEY, prop.frame).setOrigin(0.5, 1).setDepth(prop.y);
  }
  return drawPixelKitObjects(scene, plan);
}
