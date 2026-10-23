import Phaser from "phaser";
import type { LocationArea } from "../../tiled";

const OVERLAY_DEPTH = 100_000;
const OUTLINE_COLOR = 0xff6b9d;

/** 디버그 토글 시 `locations` 사각형을 반투명 외곽선과 이름으로 보여준다. */
export class LocationOverlay {
  private graphics: Phaser.GameObjects.Graphics | null = null;
  private labels: Phaser.GameObjects.Text[] = [];

  constructor(
    private readonly scene: Phaser.Scene,
    private readonly areas: readonly LocationArea[],
  ) {}

  /** 디버그가 꺼져 있으면 Text 수십 개를 만들 필요가 없으니 처음 켤 때 만든다. */
  private build(): Phaser.GameObjects.Graphics {
    const graphics = this.scene.add.graphics().setDepth(OVERLAY_DEPTH);
    graphics.fillStyle(OUTLINE_COLOR, 0.12);
    graphics.lineStyle(1, OUTLINE_COLOR, 0.7);
    this.labels = this.areas.map((area) => {
      graphics.fillRect(area.x, area.y, area.width, area.height);
      graphics.strokeRect(area.x, area.y, area.width, area.height);
      return this.scene.add
        .text(area.x + 2, area.y + 1, area.name, { fontSize: "7px", color: "#ffffff", backgroundColor: "#00000088", resolution: 4 })
        .setDepth(OVERLAY_DEPTH);
    });
    this.graphics = graphics;
    return graphics;
  }

  setVisible(visible: boolean): void {
    if (!this.graphics && !visible) return;
    (this.graphics ?? this.build()).setVisible(visible);
    for (const label of this.labels) label.setVisible(visible);
  }
}
