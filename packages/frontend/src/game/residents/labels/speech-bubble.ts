import Phaser from "phaser";
import { PIXEL_KIT_ATLAS_KEY } from "../../map/pixel-kit";
import { BUBBLE_BORDER_PX, ensureBubbleTexture, TAIL_DROP } from "./nine-patch";
import { ART_SCALE, LABEL_FONT, smoothTextTexture, SPEECH_FONT_PX, TEXT_RESOLUTION } from "./style";

/** 글자 영역 최대 폭(화면 px). 넘으면 줄바꿈한다. */
export const BUBBLE_MAX_TEXT_WIDTH = 150;
/** 틀 안쪽 여백(화면 px). */
const INNER_PAD = 3;
const FRAME_PX = BUBBLE_BORDER_PX * ART_SCALE + INNER_PAD;

/**
 * 말풍선: 9-slice 몸통 + 꼬리 + 글자. 좌표·크기는 화면 px(부모가 줌 역보정 스케일을 건다).
 * 원점은 꼬리 끝(말하는 주민의 머리 위 한 점)이고 몸통은 그 위로 자란다.
 */
export class SpeechBubble {
  readonly container: Phaser.GameObjects.Container;
  private readonly text: Phaser.GameObjects.Text;
  private readonly graphics: Phaser.GameObjects.Graphics;
  private image: Phaser.GameObjects.Image | null = null;
  private readonly usePixelKit: boolean;

  constructor(private readonly scene: Phaser.Scene, usePixelKit: boolean) {
    this.usePixelKit = usePixelKit && scene.textures.exists(PIXEL_KIT_ATLAS_KEY);
    this.text = scene.add
      .text(0, 0, "", {
        fontFamily: LABEL_FONT,
        fontSize: `${SPEECH_FONT_PX}px`,
        color: "#3b2f2f",
        align: "center",
        wordWrap: { width: BUBBLE_MAX_TEXT_WIDTH, useAdvancedWrap: true },
        resolution: TEXT_RESOLUTION,
      })
      .setOrigin(0.5, 0);
    smoothTextTexture(this.text);
    this.graphics = scene.add.graphics();
    this.container = scene.add.container(0, 0, [this.graphics, this.text]);
  }

  show(message: string): void {
    this.text.setText(message);
    smoothTextTexture(this.text);
    const bodyW = Math.ceil((this.text.width + FRAME_PX * 2) / ART_SCALE);
    const bodyH = Math.ceil((this.text.height + FRAME_PX * 2) / ART_SCALE);
    const key = this.usePixelKit ? ensureBubbleTexture(this.scene, bodyW, bodyH) : null;
    const wPx = bodyW * ART_SCALE;
    const hPx = bodyH * ART_SCALE;
    const totalH = hPx + TAIL_DROP * ART_SCALE;
    this.graphics.clear();
    this.image?.destroy();
    this.image = null;
    if (key) {
      this.image = this.scene.add.image(0, 0, key).setOrigin(0.5, 1).setScale(ART_SCALE);
      this.container.addAt(this.image, 0);
    } else {
      this.graphics.fillStyle(0xffffff, 0.95).fillRoundedRect(-wPx / 2, -totalH, wPx, hPx, 6);
      this.graphics.lineStyle(2, 0x5b4636, 1).strokeRoundedRect(-wPx / 2, -totalH, wPx, hPx, 6);
    }
    this.text.setPosition(0, -totalH + (hPx - this.text.height) / 2);
    this.container.setVisible(true);
  }

  hide(): void {
    this.container.setVisible(false);
  }
}
