import Phaser from "phaser";
import type { ResidentSnapshot } from "@agent-crossing/shared";
import { TILE_SIZE } from "../../town-layout";
import { isPixelKitEnabled, PIXEL_KIT_ATLAS_KEY } from "../map/pixel-kit";
import { NameTag, SpeechBubble } from "./labels";
import { choosePose, classifyAction, type ActionKind, type Pose, type SpotMap } from "./pose";
import { VillagerFigure } from "./villager-figure";

const BODY_COLORS = [0xf4a261, 0x8ecae6, 0xe9c46a, 0xb8a1e3, 0xf28fad, 0x95d5b2] as const;
const BODY_RADIUS = 6;
const TEXT_RESOLUTION = 4;
const SELECT_COLOR = 0xffffff;
/** 픽셀 팩 주민(16×32): 발밑은 칸 가운데보다 7px 아래, 머리 꼭대기는 그보다 약 28px 위. */
const VILLAGER_FOOT_Y = 7;
const VILLAGER_TOP_Y = -21;
const VILLAGER_WIDTH = 16;
const VILLAGER_HEIGHT = 32;
/** 머리 위 아이콘·말풍선 꼬리 끝과 머리 꼭대기 사이(월드 px). */
const HEAD_GAP = 2;
/** 이름표는 발밑에서 이만큼(월드 px) 아래에 선다. */
const TAG_GAP = 2;
/** 이름표는 모든 주민 몸 위, 말풍선은 그 위. 말풍선끼리는 나중에 뜬 것이 위(depth에 시각을 더한다). */
const TAG_DEPTH = 100_000;
const BUBBLE_DEPTH = 200_000;
/** 앉은 주민은 의자 그림 앞에 보이도록(위를 보는 의자는 등받이가 앞이라 뒤에) 칸 아랫변 바로 위로 올린다. */
const SEATED_DEPTH_BIAS = TILE_SIZE / 2 + 1;
const SLEEP_DEPTH_BIAS = 1;

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

/**
 * 주민 한 명을 그린 캐릭터(기본은 코드로 그린 원, `?art=pixel-kit`이면 픽셀 팩 주민).
 * 몸 + 선택 링 + 클릭 영역은 `container`, 이름표·행동 아이콘·말풍선은 따로 위 depth에 놓는 `overlay`에 둔다.
 * 글자는 화면 px 기준이라 매 프레임 `1/줌`으로 역보정한다.
 */
export class ResidentView {
  readonly container: Phaser.GameObjects.Container;
  private readonly overlay: Phaser.GameObjects.Container;
  private readonly ring: Phaser.GameObjects.Graphics;
  private readonly figure: VillagerFigure | null;
  private readonly tagLayer: Phaser.GameObjects.Container;
  private readonly bubbleLayer: Phaser.GameObjects.Container;
  private readonly bubble: SpeechBubble;
  private readonly iconLayer: Phaser.GameObjects.Container;
  private readonly iconBack: Phaser.GameObjects.Image | null;
  private readonly iconImage: Phaser.GameObjects.Image | null;
  private readonly emojiText: Phaser.GameObjects.Text;
  /** 머리 위 기준(아이콘·말풍선을 이 위에 단다). */
  private readonly topY: number;
  private bubbleShown: string | null = null;
  private bubbleDepth = BUBBLE_DEPTH;
  private tile = { x: 0, y: 0 };
  private pxY = 0;
  private shownKind: ActionKind | "emoji" | null = null;

  constructor(
    private readonly scene: Phaser.Scene,
    resident: ResidentSnapshot,
    onSelect: (id: string) => void,
    private readonly spots: SpotMap,
  ) {
    const usePixelKit = isPixelKitEnabled() && scene.textures.exists(PIXEL_KIT_ATLAS_KEY);
    this.figure = usePixelKit ? new VillagerFigure(scene, resident.resident_id, VILLAGER_FOOT_Y) : null;
    this.topY = usePixelKit ? VILLAGER_TOP_Y : -BODY_RADIUS;
    const body = this.figure?.sprite ?? drawCircleBody(scene, resident.resident_id);
    const footY = usePixelKit ? VILLAGER_FOOT_Y : BODY_RADIUS;

    this.ring = scene.add.graphics();
    const ringY = usePixelKit ? footY - 1 : 0;
    if (usePixelKit) this.ring.lineStyle(1, SELECT_COLOR, 1).strokeEllipse(0, ringY, VILLAGER_WIDTH + 4, 8);
    else this.ring.lineStyle(1, SELECT_COLOR, 1).strokeCircle(0, 0, BODY_RADIUS + 2);
    this.ring.setVisible(false);

    // 클릭 영역은 보이는 몸 크기(픽셀 팩이면 16×32)에 맞춘다.
    const hitHeight = usePixelKit ? VILLAGER_HEIGHT : BODY_RADIUS * 2;
    const hitWidth = usePixelKit ? VILLAGER_WIDTH : BODY_RADIUS * 2;
    const hitCenterY = usePixelKit ? footY - VILLAGER_HEIGHT / 2 : 0;
    const hit = scene.add.zone(0, hitCenterY, hitWidth, hitHeight);
    hit.setInteractive({ useHandCursor: true });
    hit.on("pointerup", (pointer: Phaser.Input.Pointer) => {
      // 카메라 드래그 끝의 pointerup은 선택으로 보지 않는다.
      if (pointer.getDistance() < 4) onSelect(resident.resident_id);
    });
    this.container = scene.add.container(0, 0, [this.ring, body, hit]);

    const hasIcons = usePixelKit && scene.textures.get(PIXEL_KIT_ATLAS_KEY).has("act_bubble");
    this.iconBack = hasIcons ? scene.add.image(0, 0, PIXEL_KIT_ATLAS_KEY, "act_bubble").setOrigin(0.5, 1) : null;
    this.iconImage = hasIcons ? scene.add.image(0, 0, PIXEL_KIT_ATLAS_KEY, "act_work").setOrigin(0.5, 1) : null;
    this.emojiText = scene.add.text(0, 0, "", { fontSize: "9px", resolution: TEXT_RESOLUTION }).setOrigin(0.5, 1);
    this.iconLayer = scene.add.container(0, this.topY - HEAD_GAP, [
      ...(this.iconBack && this.iconImage ? [this.iconBack, this.iconImage] : []),
      this.emojiText,
    ]);

    const tag = new NameTag(scene, resident.display_name, usePixelKit);
    this.tagLayer = scene.add.container(0, footY + TAG_GAP, [tag.container]);
    this.bubble = new SpeechBubble(scene, usePixelKit);
    this.bubbleLayer = scene.add.container(0, this.topY - HEAD_GAP, [this.bubble.container]);
    this.overlay = scene.add.container(0, 0, [this.iconLayer, this.tagLayer, this.bubbleLayer]);
    this.overlay.setDepth(TAG_DEPTH);
    this.hideBubble();
    this.setIcon(null, null);
  }

  /** 타일 좌표(소수 허용)로 옮긴다. 아래쪽 주민이 위에 그려지도록 depth를 y로 둔다. */
  placeAtTile(x: number, y: number): void {
    const px = (x + 0.5) * TILE_SIZE;
    const py = (y + 0.5) * TILE_SIZE;
    this.pxY = py;
    this.container.setPosition(px, py);
    this.container.setDepth(py);
    this.overlay.setPosition(px, py);
    this.figure?.track(x, y);
  }

  update(resident: ResidentSnapshot, bubble: string | null, selected: boolean): void {
    this.ring.setVisible(selected);
    this.tile = { x: resident.tile.x, y: resident.tile.y };
    const moving = this.figure?.isMoving ?? false;
    const kind = classifyAction({
      action_description: resident.action_description,
      emoji: resident.emoji,
      talking: bubble !== null,
      moving,
    });
    this.applyPose(kind, moving);
    this.syncLabels(resident, kind, bubble);
  }

  destroy(): void {
    this.container.destroy();
    this.overlay.destroy();
  }

  private applyPose(kind: ActionKind | null, moving: boolean): void {
    if (!this.figure) return;
    const spot = moving ? null : this.spots.spotAt(this.tile.x, this.tile.y);
    const pose = choosePose({ kind, moving, spot });
    const bedFoot = pose.bed ? pose.bed.bottomPx - this.pxY : VILLAGER_FOOT_Y;
    this.figure.apply(pose, bedFoot);
    this.container.setDepth(this.pxY + this.depthBias(pose));
  }

  private depthBias(pose: Pose): number {
    if (pose.act === "sleep") return VILLAGER_HEIGHT + SLEEP_DEPTH_BIAS;
    if (pose.act === "sit" && pose.facing !== "up") return SEATED_DEPTH_BIAS;
    return 0;
  }

  private syncLabels(resident: ResidentSnapshot, kind: ActionKind | null, bubble: string | null): void {
    const inverse = 1 / this.scene.cameras.main.zoom;
    this.tagLayer.setScale(inverse);
    this.bubbleLayer.setScale(inverse);
    if (bubble !== this.bubbleShown) {
      if (bubble) this.showBubble(bubble);
      else this.hideBubble();
    }
    // 말풍선이 있으면 그 자리를 말풍선이 쓰니 아이콘은 숨긴다.
    this.setIcon(bubble ? null : kind, resident.emoji);
  }

  private setIcon(kind: ActionKind | null, emoji: string | null): void {
    const frameName = kind ? `act_${kind}` : null;
    const hasFrame = frameName !== null && this.iconImage !== null && this.scene.textures.get(PIXEL_KIT_ATLAS_KEY).has(frameName);
    const next: ActionKind | "emoji" | null = hasFrame ? kind : emoji && !hasFrame ? "emoji" : null;
    // 아이콘이 없고 이모지만 있을 때는 이모지 글자로 대체한다(매핑이 없을 때만).
    if (next === this.shownKind && next !== "emoji") return;
    this.shownKind = next;
    const iconVisible = next !== null && next !== "emoji";
    this.iconBack?.setVisible(iconVisible);
    this.iconImage?.setVisible(iconVisible);
    if (iconVisible && frameName) this.iconImage?.setFrame(frameName, true, false);
    this.emojiText.setText(next === "emoji" ? (emoji ?? "") : "").setVisible(next === "emoji");
  }

  private showBubble(text: string): void {
    this.bubbleShown = text;
    this.bubble.show(text);
    this.bubbleDepth = BUBBLE_DEPTH + this.scene.time.now * 0.001;
    this.overlay.setDepth(this.bubbleDepth);
  }

  private hideBubble(): void {
    this.bubbleShown = null;
    this.bubble.hide();
    this.overlay.setDepth(TAG_DEPTH);
  }
}
