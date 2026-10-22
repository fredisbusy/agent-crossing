import Phaser from "phaser";
import { PIXEL_KIT_ATLAS_KEY } from "../map/pixel-kit";
import { villagerLookFor } from "./looks";
import type { Pose, PoseAct } from "./pose";

const FACINGS = ["down", "up", "right"] as const;
type SheetFacing = (typeof FACINGS)[number];
type Facing = SheetFacing | "left";

/** 동작별 애니 프레임 수와 프레임당 시간(ms). 출처: stardewrogue `people.ts` META. */
const ACT_ANIMS: Readonly<Record<Exclude<PoseAct, "sleep">, { ms: readonly number[] }>> = {
  idle: { ms: [2400, 150] },
  walk: { ms: [150, 150, 150, 150] },
  sit: { ms: [1000] },
  work: { ms: [280, 280] },
  talk: { ms: [240, 200] },
};
const SLEEP_MS = [900, 900] as const;
/** 프레임 사이 이동이 이 타일 수보다 작으면 멈춘 것으로 본다. */
const MOVE_EPSILON = 0.002;
/** 한 프레임에 이만큼(타일) 넘게 옮겨졌으면 걸은 게 아니라 순간이동이다(걷기 포즈로 보지 않는다). */
const TELEPORT_TILES = 1.5;
/** 앉으면 몸을 이만큼(월드 px) 내려 엉덩이가 의자 좌석 높이에 오게 한다. */
const SIT_DROP = 3;

const animKey = (look: string, act: PoseAct, facing: SheetFacing | null): string =>
  act === "sleep" ? `villager_${look}_sleep` : `villager_${look}_${act}_${facing ?? "down"}`;

function createAnim(scene: Phaser.Scene, key: string, ms: readonly number[]): void {
  if (scene.anims.exists(key)) return;
  scene.anims.create({
    key,
    frames: ms.map((duration, i) => ({ key: PIXEL_KIT_ATLAS_KEY, frame: `${key}_${i}`, duration })),
    repeat: -1,
  });
}

function ensureAnims(scene: Phaser.Scene, look: string): void {
  for (const facing of FACINGS) {
    for (const [act, spec] of Object.entries(ACT_ANIMS)) {
      createAnim(scene, animKey(look, act as PoseAct, facing), spec.ms);
    }
  }
  createAnim(scene, animKey(look, "sleep", null), SLEEP_MS);
}

/** 포즈에 맞춰 서기·걷기·앉기·일하기·말하기·자기 애니를 고르는 주민 스프라이트. 발밑이 (0, `footY`)에 온다. */
export class VillagerFigure {
  readonly sprite: Phaser.GameObjects.Sprite;
  private readonly look: string;
  private facing: Facing = "down";
  private last: { x: number; y: number } | null = null;
  private moving = false;

  constructor(scene: Phaser.Scene, residentId: string, private readonly footY: number) {
    this.look = villagerLookFor(residentId);
    ensureAnims(scene, this.look);
    this.sprite = scene.add.sprite(0, footY, PIXEL_KIT_ATLAS_KEY, `${animKey(this.look, "idle", "down")}_0`).setOrigin(0.5, 1);
    this.sprite.play(animKey(this.look, "idle", "down"));
  }

  get isMoving(): boolean {
    return this.moving;
  }

  /** 타일 좌표가 바뀔 때마다 부른다. 움직였는지 갱신하고 움직인 방향으로 몸을 돌린다. */
  track(x: number, y: number): boolean {
    const dx = this.last ? x - this.last.x : 0;
    const dy = this.last ? y - this.last.y : 0;
    this.last = { x, y };
    const jumped = Math.abs(dx) > TELEPORT_TILES || Math.abs(dy) > TELEPORT_TILES;
    this.moving = !jumped && (Math.abs(dx) > MOVE_EPSILON || Math.abs(dy) > MOVE_EPSILON);
    if (this.moving) this.facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
    return this.moving;
  }

  /**
   * 포즈를 그린다. `sleepFootY`는 침대에서 잘 때 스프라이트 발밑(컨테이너 기준 px)이다.
   * 의자가 방향을 정하면 몸도 그 방향으로 돌아선다.
   */
  apply(pose: Pose, sleepFootY: number): void {
    if (pose.facing) this.facing = pose.facing;
    const sheetFacing: SheetFacing = this.facing === "left" ? "right" : this.facing;
    const key = animKey(this.look, pose.act, sheetFacing);
    this.sprite.setFlipX(pose.act !== "sleep" && this.facing === "left");
    this.sprite.setY(pose.act === "sleep" ? sleepFootY : this.footY + (pose.act === "sit" ? SIT_DROP : 0));
    if (this.sprite.anims.currentAnim?.key !== key) this.sprite.play(key);
  }
}
