import Phaser from "phaser";
import type { LocationArea } from "./locations";

const OVERLAY_DEPTH = 100_000;
const OUTLINE_COLOR = 0xff6b9d;

/** 디버그 토글 시 `locations` 사각형을 반투명 외곽선과 이름으로 보여준다. */
export class LocationOverlay {
  private readonly graphics: Phaser.GameObjects.Graphics;
  private readonly labels: Phaser.GameObjects.Text[];

  constructor(scene: Phaser.Scene, areas: readonly LocationArea[]) {
    this.graphics = scene.add.graphics().setDepth(OVERLAY_DEPTH);
    this.graphics.fillStyle(OUTLINE_COLOR, 0.12);
    this.graphics.lineStyle(1, OUTLINE_COLOR, 0.7);
    this.labels = areas.map((area) => {
      this.graphics.fillRect(area.x, area.y, area.width, area.height);
      this.graphics.strokeRect(area.x, area.y, area.width, area.height);
      return scene.add
        .text(area.x + 2, area.y + 1, area.name, { fontSize: "7px", color: "#ffffff", backgroundColor: "#00000088", resolution: 4 })
        .setDepth(OVERLAY_DEPTH);
    });
    this.setVisible(false);
  }

  setVisible(visible: boolean): void {
    this.graphics.setVisible(visible);
    for (const label of this.labels) label.setVisible(visible);
  }
}
