import Phaser from "phaser";
import type { ResidentSnapshot } from "@agent-crossing/shared";
import { TILE_SIZE } from "../../town-layout";
import { isPixelKitEnabled, PIXEL_KIT_ATLAS_KEY } from "../map/pixel-kit";
import { VillagerFigure } from "./villager-figure";

const BODY_COLORS = [0xf4a261, 0x8ecae6, 0xe9c46a, 0xb8a1e3, 0xf28fad, 0x95d5b2] as const;
const BODY_RADIUS = 6;
const TEXT_RESOLUTION = 4;
const SELECT_COLOR = 0xffffff;
/** 픽셀 팩 주민(16×32): 발밑은 칸 가운데보다 7px 아래, 머리 꼭대기는 그보다 약 28px 위. */
const VILLAGER_FOOT_Y = 7;
const VILLAGER_TOP_Y = -21;

/** id에서 항상 같은 몸 색을 고른다. */
export function bodyColorFor(id: string): number {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return BODY_COLORS[hash % BODY_COLORS.length];
}

function drawCircleBody(scene: Phaser.Scene, id: string): Phaser.GameObjects.Graphics {
  const body = scene.add.graphics();
  body.fillStyle(0x000000, 0.18).fillEllipse(0, BODY_RADIUS - 1, BODY_RADIUS * 2, 5);
  body.fillStyle(bodyColorFor(id), 1).fillCircle(0, 0, BODY_RADIUS);
  body.lineStyle(1, 0x5b4636, 1).strokeCircle(0, 0, BODY_RADIUS);
  body.fillStyle(0x3b2f2f, 1).fillCircle(-2, -1, 1).fillCircle(2, -1, 1);
  return body;
}

/** 주민 한 명을 그린 캐릭터(기본은 코드로 그린 원, `?art=pixel-kit`이면 픽셀 팩 주민): 원형 몸, 이름표, 머리 위 이모지, 말풍선. */
export class ResidentView {
  readonly container: Phaser.GameObjects.Container;
  private readonly ring: Phaser.GameObjects.Graphics;
  private readonly emoji: Phaser.GameObjects.Text;
  private readonly bubbleBox: Phaser.GameObjects.Graphics;
  private readonly bubbleText: Phaser.GameObjects.Text;
  private readonly figure: VillagerFigure | null;
  /** 머리 위 기준(이모지·말풍선을 이 위에 단다). */
  private readonly topY: number;
  private bubbleShown: string | null = null;

  constructor(scene: Phaser.Scene, resident: ResidentSnapshot, onSelect: (id: string) => void) {
    const usePixelKit = isPixelKitEnabled() && scene.textures.exists(PIXEL_KIT_ATLAS_KEY);
    this.figure = usePixelKit ? new VillagerFigure(scene, resident.resident_id, VILLAGER_FOOT_Y) : null;
    this.topY = usePixelKit ? VILLAGER_TOP_Y : -BODY_RADIUS;
    const body = this.figure?.sprite ?? drawCircleBody(scene, resident.resident_id);

    this.ring = scene.add.graphics();
    this.ring.lineStyle(1, SELECT_COLOR, 1).strokeCircle(0, 0, BODY_RADIUS + 2).setVisible(false);

    const name = scene.add
      .text(0, (usePixelKit ? VILLAGER_FOOT_Y : BODY_RADIUS) + 3, resident.display_name, {
        fontSize: "6px",
        color: "#ffffff",
        backgroundColor: "#3b2f2fcc",
        padding: { x: 1, y: 0 },
        resolution: TEXT_RESOLUTION,
      })
      .setOrigin(0.5, 0);

    this.emoji = scene.add
      .text(0, this.topY - 2, "", { fontSize: "9px", resolution: TEXT_RESOLUTION })
      .setOrigin(0.5, 1);

    this.bubbleBox = scene.add.graphics();
    this.bubbleText = scene.add
      .text(0, 0, "", {
        fontSize: "6px",
        color: "#3b2f2f",
        wordWrap: { width: 70 },
        align: "center",
        resolution: TEXT_RESOLUTION,
      })
      .setOrigin(0.5, 1);

    this.container = scene.add.container(0, 0, [this.ring, body, name, this.emoji, this.bubbleBox, this.bubbleText]);
    this.container.setSize(BODY_RADIUS * 2, BODY_RADIUS * 2);
    this.container.setInteractive({ useHandCursor: true });
    this.container.on("pointerup", (pointer: Phaser.Input.Pointer) => {
      // 카메라 드래그 끝의 pointerup은 선택으로 보지 않는다.
      if (pointer.getDistance() < 4) onSelect(resident.resident_id);
    });
    this.hideBubble();
  }

  /** 타일 좌표(소수 허용)로 옮긴다. 아래쪽 주민이 위에 그려지도록 depth를 y로 둔다. */
  placeAtTile(x: number, y: number): void {
    const px = (x + 0.5) * TILE_SIZE;
    const py = (y + 0.5) * TILE_SIZE;
    this.container.setPosition(px, py);
    this.container.setDepth(py);
    this.figure?.moveTo(x, y);
  }

  update(resident: ResidentSnapshot, bubble: string | null, selected: boolean): void {
    this.emoji.setText(resident.emoji ?? "");
    this.ring.setVisible(selected);
    if (bubble !== this.bubbleShown) {
      if (bubble) this.showBubble(bubble);
      else this.hideBubble();
    }
  }

  destroy(): void {
    this.container.destroy();
  }

  private showBubble(text: string): void {
    this.bubbleShown = text;
    this.bubbleText.setText(text).setVisible(true);
    const padding = 3;
    const width = this.bubbleText.width + padding * 2;
    const height = this.bubbleText.height + padding * 2;
    const bottom = this.topY - 13;
    this.bubbleText.setPosition(0, bottom - padding);
    this.bubbleBox.clear();
    this.bubbleBox.fillStyle(0xffffff, 0.95).fillRoundedRect(-width / 2, bottom - height, width, height, 3);
    this.bubbleBox.lineStyle(1, 0x5b4636, 1).strokeRoundedRect(-width / 2, bottom - height, width, height, 3);
    this.bubbleBox.setVisible(true);
  }

  private hideBubble(): void {
    this.bubbleShown = null;
    this.bubbleText.setVisible(false);
    this.bubbleBox.setVisible(false);
  }
}
