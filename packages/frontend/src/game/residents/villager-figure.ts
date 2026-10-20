import Phaser from "phaser";
import { PIXEL_KIT_ATLAS_KEY } from "../map/pixel-kit";

/** stardewrogue `people.ts`의 `LOOKS` 키. 주민 id 해시로 한 벌을 고른다. */
const VILLAGER_LOOKS = ["a", "b", "c", "d", "e"] as const;
const FACINGS = ["down", "up", "right"] as const;
type Facing = (typeof FACINGS)[number] | "left";
/** stardewrogue `people.ts` META 애니 시간(초기값). */
const IDLE_MS = [2400, 150] as const;
const WALK_MS = 150;
const WALK_FRAMES = 4;
/** 프레임 사이 이동이 이 타일 수보다 작으면 멈춘 것으로 본다. */
const MOVE_EPSILON = 0.002;

export function villagerLookFor(id: string): string {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return VILLAGER_LOOKS[hash % VILLAGER_LOOKS.length];
}

const animKey = (look: string, act: "idle" | "walk", facing: (typeof FACINGS)[number]): string =>
  `villager_${look}_${act}_${facing}`;

function ensureAnims(scene: Phaser.Scene, look: string): void {
  for (const facing of FACINGS) {
    const idle = animKey(look, "idle", facing);
    if (!scene.anims.exists(idle)) {
      scene.anims.create({
        key: idle,
        frames: IDLE_MS.map((duration, i) => ({ key: PIXEL_KIT_ATLAS_KEY, frame: `${idle}_${i}`, duration })),
        repeat: -1,
      });
    }
    const walk = animKey(look, "walk", facing);
    if (!scene.anims.exists(walk)) {
      scene.anims.create({
        key: walk,
        frames: Array.from({ length: WALK_FRAMES }, (_, i) => ({ key: PIXEL_KIT_ATLAS_KEY, frame: `${walk}_${i}`, duration: WALK_MS })),
        repeat: -1,
      });
    }
  }
}

/** 걷는 방향에 맞춰 서기·걷기 애니를 고르는 주민 스프라이트. 발밑이 (0, `footY`)에 온다. */
export class VillagerFigure {
  readonly sprite: Phaser.GameObjects.Sprite;
  private readonly look: string;
  private facing: Facing = "down";
  private last: { x: number; y: number } | null = null;

  constructor(scene: Phaser.Scene, residentId: string, footY: number) {
    this.look = villagerLookFor(residentId);
    ensureAnims(scene, this.look);
    this.sprite = scene.add.sprite(0, footY, PIXEL_KIT_ATLAS_KEY, `${animKey(this.look, "idle", "down")}_0`).setOrigin(0.5, 1);
    this.sprite.play(animKey(this.look, "idle", "down"));
  }

  /** 타일 좌표가 바뀔 때마다 부른다. 움직임 방향으로 몸을 돌리고, 멈추면 서기로 돌아간다. */
  moveTo(x: number, y: number): void {
    const dx = this.last ? x - this.last.x : 0;
    const dy = this.last ? y - this.last.y : 0;
    this.last = { x, y };
    const moving = Math.abs(dx) > MOVE_EPSILON || Math.abs(dy) > MOVE_EPSILON;
    if (moving) this.facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
    const sheetFacing = this.facing === "left" ? "right" : this.facing;
    const key = animKey(this.look, moving ? "walk" : "idle", sheetFacing);
    this.sprite.setFlipX(this.facing === "left");
    if (this.sprite.anims.currentAnim?.key !== key) this.sprite.play(key);
  }
}
