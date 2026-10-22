import Phaser from "phaser";
import { PIXEL_KIT_ATLAS_KEY } from "../../map/pixel-kit";
import { ensureTagTexture, TAG_ART_HEIGHT, TAG_CAP_WIDTH } from "./nine-patch";
import { ART_SCALE, LABEL_FONT, NAME_FONT_PX, smoothTextTexture, TEXT_RESOLUTION } from "./style";

/** 글자 좌우 여백(화면 px). */
const TEXT_PAD_X = 4;

/**
 * 이름표. 좌표·크기는 모두 화면 px(부모 컨테이너가 줌 역보정 스케일을 건다).
 * 픽셀 팩이 없으면 어두운 바탕 글자로 대체한다. 원점은 이름표 윗변 가운데.
 */
export class NameTag {
  readonly container: Phaser.GameObjects.Container;
  /** 화면 px 크기. */
  readonly width: number;
  readonly height: number;

  constructor(scene: Phaser.Scene, name: string, usePixelKit: boolean) {
    const text = scene.add
      .text(0, 0, name, {
        fontFamily: LABEL_FONT,
        fontSize: `${NAME_FONT_PX}px`,
        fontStyle: "bold",
        color: "#fff6e0",
        resolution: TEXT_RESOLUTION,
      })
      .setOrigin(0.5, 0.5);
    smoothTextTexture(text);
    const height = TAG_ART_HEIGHT * ART_SCALE;
    this.height = height;
    this.width = Math.ceil((text.width + TEXT_PAD_X * 2) / ART_SCALE) * ART_SCALE;
    const children: Phaser.GameObjects.GameObject[] = [];
    const key = usePixelKit && scene.textures.exists(PIXEL_KIT_ATLAS_KEY) ? this.bake(scene, text.width) : null;
    if (key) {
      const image = scene.add.image(0, 0, key).setOrigin(0.5, 0).setScale(ART_SCALE);
      children.push(image);
    } else {
      const bg = scene.add.rectangle(0, 0, text.width + TEXT_PAD_X * 2, height, 0x3b2f2f, 0.85).setOrigin(0.5, 0);
      children.push(bg);
    }
    text.setPosition(0, height / 2 + 0.5);
    children.push(text);
    this.container = scene.add.container(0, 0, children);
  }

  private bake(scene: Phaser.Scene, textWidth: number): string | null {
    const artWidth = Math.ceil((textWidth + TEXT_PAD_X * 2) / ART_SCALE);
    return ensureTagTexture(scene, artWidth - TAG_CAP_WIDTH * 2);
  }
}
