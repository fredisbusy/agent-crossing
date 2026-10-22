import Phaser from "phaser";
import type { LocationArea } from "../map/locations";
import { LIGHT_OBJECT_NAME, type MapSprite } from "../map/objects";
import { isPixelKitEnabled, PIXEL_KIT_ATLAS_KEY } from "../map/pixel-kit";
import { indoorAreas } from "./indoor-areas";
import { daylightForSimTime, multiplyColorOf, type DaylightTint } from "./daylight-phase";

/** 틴트는 주민(깊이=y)보다 위, 디버그 오버레이(100000)보다 아래. */
const TINT_DEPTH = 90_000;
const LIGHT_DEPTH = TINT_DEPTH + 1;
const LAMP_FRAME = "lamp_post";
const LAMP_LIT_FRAME = "lamp_post_lit";
const LIGHT_POOL_FRAME = "light_pool";
/** 어둠이 이 값보다 옅으면 가로등 불을 끈다. */
const LAMP_ON_DARKNESS = 0.15;
const LIGHT_POOL_MAX_ALPHA = 0.85;
/** 실내는 밤에 따뜻한 색을 더해 주민이 보이게 한다. */
const INDOOR_GLOW_COLOR = 0xffb866;
const INDOOR_GLOW_MAX_ALPHA = 0.3;
export interface DaylightInput {
  widthPx: number;
  heightPx: number;
  areas: readonly LocationArea[];
  decor: readonly MapSprite[];
}

/** 맵 전체 MULTIPLY 틴트와, 픽셀 팩 모드의 가로등 빛·실내 불빛을 sim 시각으로 갱신한다. */
export class DaylightLayer {
  private readonly tint: Phaser.GameObjects.Rectangle;
  private readonly pools: Phaser.GameObjects.Image[] = [];
  private readonly lamps: Phaser.GameObjects.Image[] = [];
  private readonly glows: Phaser.GameObjects.Rectangle[] = [];
  private lastKey = "";

  constructor(scene: Phaser.Scene, input: DaylightInput) {
    this.tint = scene.add
      .rectangle(0, 0, input.widthPx, input.heightPx, 0xffffff)
      .setOrigin(0, 0)
      .setDepth(TINT_DEPTH)
      .setBlendMode(Phaser.BlendModes.MULTIPLY);
    for (const area of indoorAreas(input.areas)) {
      this.glows.push(
        scene.add
          .rectangle(area.x, area.y, area.width, area.height, INDOOR_GLOW_COLOR)
          .setOrigin(0, 0)
          .setDepth(LIGHT_DEPTH)
          .setBlendMode(Phaser.BlendModes.ADD)
          .setVisible(false),
      );
    }
    if (!isPixelKitEnabled() || !scene.textures.exists(PIXEL_KIT_ATLAS_KEY)) return;
    for (const sprite of input.decor) {
      if (sprite.frame === LIGHT_OBJECT_NAME) {
        this.pools.push(
          scene.add
            .image(sprite.x + sprite.width / 2, sprite.y + sprite.height / 2, PIXEL_KIT_ATLAS_KEY, LIGHT_POOL_FRAME)
            .setDepth(LIGHT_DEPTH)
            .setBlendMode(Phaser.BlendModes.ADD)
            .setVisible(false),
        );
      } else if (sprite.frame === LAMP_FRAME) {
        this.lamps.push(
          scene.add
            .image(sprite.x, sprite.y, PIXEL_KIT_ATLAS_KEY, LAMP_LIT_FRAME)
            .setOrigin(0, 0)
            .setDepth(LIGHT_DEPTH)
            .setVisible(false),
        );
      }
    }
  }

  /** 시뮬레이션 시각(ISO)에 맞춰 갱신한다. 틴트가 같으면 아무것도 하지 않는다. */
  setSimTime(iso: string): DaylightTint {
    const tint = daylightForSimTime(iso);
    const key = `${tint.color}:${tint.alpha.toFixed(3)}`;
    if (key !== this.lastKey) {
      this.lastKey = key;
      this.apply(tint);
    }
    return tint;
  }

  private apply(tint: DaylightTint): void {
    this.tint.setFillStyle(multiplyColorOf(tint), 1).setVisible(tint.alpha > 0);
    const lampsOn = tint.darkness > LAMP_ON_DARKNESS;
    for (const pool of this.pools) pool.setVisible(lampsOn).setAlpha(tint.darkness * LIGHT_POOL_MAX_ALPHA);
    for (const lamp of this.lamps) lamp.setVisible(lampsOn);
    for (const glow of this.glows) glow.setVisible(lampsOn).setAlpha(tint.darkness * INDOOR_GLOW_MAX_ALPHA);
  }
}
