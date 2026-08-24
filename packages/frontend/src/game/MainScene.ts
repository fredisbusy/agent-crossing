import Phaser from "phaser";
import type { SpatialAgentState } from "@agent-crossing/shared";
import {
  getLayer,
  getProperty,
  parseColor,
  townMap,
  type TiledObject,
} from "../map/tiled";
import { useGameStore } from "../stores/game.store";
import { createPixelTextures, TILE, TILE_SIZE } from "./pixelTextures";

const WORLD_WIDTH = townMap.width * townMap.tilewidth;
const WORLD_HEIGHT = townMap.height * townMap.tileheight;
const PIXEL_FONT = '"Courier New", monospace';

interface AgentView {
  container: Phaser.GameObjects.Container;
  body: Phaser.GameObjects.Rectangle;
  leftLeg: Phaser.GameObjects.Rectangle;
  rightLeg: Phaser.GameObjects.Rectangle;
  bubble: Phaser.GameObjects.Text;
  nameplate: Phaser.GameObjects.Text;
  lastX: number;
  lastY: number;
}

function tileKeyAt(x: number, y: number): string {
  const centerX = x * TILE_SIZE + TILE_SIZE / 2;
  const centerY = y * TILE_SIZE + TILE_SIZE / 2;
  const plaza = getLayer("locations").find(
    (location) =>
      getProperty(location, "kind") === "plaza" &&
      contains(location, centerX, centerY),
  );
  if (plaza) return TILE.plaza;

  const park = getLayer("locations").find(
    (location) =>
      getProperty(location, "kind") === "park" &&
      contains(location, centerX, centerY),
  );
  const pond = getLayer("collision").find(
    (collision) =>
      collision.type === "water" && contains(collision, centerX, centerY),
  );
  if (pond) return TILE.water;
  if (park) return (x + y) % 5 === 0 ? TILE.grassDark : TILE.park;
  if (isPathTile(centerX, centerY)) return TILE.path;
  return (x * 3 + y * 5) % 7 === 0 ? TILE.grassDark : TILE.grass;
}

function contains(object: TiledObject, x: number, y: number): boolean {
  return (
    x >= object.x &&
    x < object.x + (object.width ?? 0) &&
    y >= object.y &&
    y < object.y + (object.height ?? 0)
  );
}

function distanceToSegment(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
): number {
  const dx = bx - ax;
  const dy = by - ay;
  if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
  const progress = Phaser.Math.Clamp(
    ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy),
    0,
    1,
  );
  return Math.hypot(px - (ax + progress * dx), py - (ay + progress * dy));
}

function isPathTile(x: number, y: number): boolean {
  return getLayer("paths").some((path) => {
    const points = path.polyline ?? [];
    return points.slice(1).some((point, index) => {
      const previous = points[index];
      return (
        distanceToSegment(
          x,
          y,
          path.x + previous.x,
          path.y + previous.y,
          path.x + point.x,
          path.y + point.y,
        ) <= 25
      );
    });
  });
}

export class MainScene extends Phaser.Scene {
  private readonly agentViews = new Map<string, AgentView>();
  private unsubscribeStore?: () => void;
  private followedAgentId = "Jiho";
  private cursors?: Phaser.Types.Input.Keyboard.CursorKeys;
  private dragOrigin?: Phaser.Math.Vector2;

  constructor() {
    super("MainScene");
  }

  create(): void {
    createPixelTextures(this);
    this.cameras.main
      .setBackgroundColor("#173b2b")
      .setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);
    this.physics.world.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);

    this.drawTileWorld();
    this.drawBuildings();
    this.drawDecorations();
    this.drawInteractables();
    this.drawAgents();
    this.drawWorldTitle();
    this.configureCamera();

    this.unsubscribeStore = useGameStore.subscribe((state) =>
      this.applyAgentStates(state.agents),
    );
    this.applyAgentStates(useGameStore.getState().agents);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () =>
      this.unsubscribeStore?.(),
    );
  }

  update(_time: number, delta: number): void {
    if (!this.cursors) return;
    const camera = this.cameras.main;
    const speed = (delta / camera.zoom) * 0.48;
    let moved = false;
    if (this.cursors.left.isDown) {
      camera.scrollX -= speed;
      moved = true;
    }
    if (this.cursors.right.isDown) {
      camera.scrollX += speed;
      moved = true;
    }
    if (this.cursors.up.isDown) {
      camera.scrollY -= speed;
      moved = true;
    }
    if (this.cursors.down.isDown) {
      camera.scrollY += speed;
      moved = true;
    }
    if (moved) this.stopFollowing();
  }

  private drawTileWorld(): void {
    const ground = this.add.container(0, 0).setDepth(0);
    for (let y = 0; y < townMap.height; y += 1) {
      for (let x = 0; x < townMap.width; x += 1) {
        ground.add(
          this.add
            .image(x * TILE_SIZE, y * TILE_SIZE, tileKeyAt(x, y))
            .setOrigin(0),
        );
      }
    }

    const border = this.add.graphics().setDepth(2);
    border.lineStyle(8, 0x245f40, 1);
    border.strokeRect(4, 4, WORLD_WIDTH - 8, WORLD_HEIGHT - 8);
  }

  private drawBuildings(): void {
    for (const location of getLayer("locations")) {
      const kind = getProperty(location, "kind", "building");
      if (kind === "plaza" || kind === "park") continue;
      this.drawPixelBuilding(location, kind);
    }
  }

  private drawPixelBuilding(location: TiledObject, kind: string): void {
    const width = location.width ?? 0;
    const height = location.height ?? 0;
    const bodyColor = parseColor(getProperty(location, "color"), 0xd58c68);
    const graphics = this.add.graphics().setDepth(location.y + height - 8);
    const left = location.x + 16;
    const right = location.x + width - 16;
    const roofTop = location.y + 12;
    const bodyTop = location.y + 70;
    const bottom = location.y + height - 12;

    graphics.fillStyle(0x294c35, 0.32);
    graphics.fillRect(left + 8, bodyTop + 12, right - left, bottom - bodyTop);
    graphics.fillStyle(bodyColor, 1);
    graphics.fillRect(left, bodyTop, right - left, bottom - bodyTop);
    graphics.fillStyle(0x694337, 1);
    for (let step = 0; step < 7; step += 1) {
      graphics.fillRect(
        left + step * 8,
        roofTop + step * 8,
        right - left - step * 16,
        9,
      );
    }
    graphics.fillStyle(0x8c5b45, 1);
    graphics.fillRect(left + 12, bodyTop - 8, right - left - 24, 9);
    graphics.fillStyle(0x54372f, 1);
    graphics.fillRect(location.x + width / 2 - 13, bottom - 45, 26, 45);
    graphics.fillStyle(0xf8cf68, 1);
    graphics.fillRect(location.x + width / 2 + 7, bottom - 23, 4, 4);

    const windowColor = kind === "library" ? 0xa9dcf0 : 0xffdfa0;
    for (const windowX of [left + 27, right - 51]) {
      graphics.fillStyle(0xf3efe0, 1);
      graphics.fillRect(windowX - 3, bodyTop + 25, 30, 26);
      graphics.fillStyle(windowColor, 1);
      graphics.fillRect(windowX, bodyTop + 28, 24, 20);
      graphics.fillStyle(0xd3b46e, 1);
      graphics.fillRect(windowX + 10, bodyTop + 28, 3, 20);
      graphics.fillRect(windowX, bodyTop + 36, 24, 3);
    }

    if (kind === "cafe" || kind === "market") {
      graphics.fillStyle(0xf4e8c8, 1);
      graphics.fillRect(left + 28, bodyTop + 4, right - left - 56, 18);
      const awningColor = kind === "cafe" ? 0xb94d4d : 0x367f61;
      for (let x = left + 30; x < right - 31; x += 16) {
        graphics.fillStyle(awningColor, 1);
        graphics.fillRect(x, bodyTop + 5, 8, 17);
      }
    }

    const sign = this.add
      .text(
        location.x + width / 2,
        location.y - 4,
        location.name.toUpperCase(),
        {
          fontFamily: PIXEL_FONT,
          fontSize: "10px",
          fontStyle: "bold",
          color: "#fff8d9",
          backgroundColor: "#253e31",
          padding: { x: 6, y: 3 },
        },
      )
      .setOrigin(0.5)
      .setDepth(location.y + height + 1)
      .setResolution(1);
    sign.setShadow(2, 2, "#15271f", 0, false, true);
  }

  private drawDecorations(): void {
    for (const decoration of getLayer("decorations")) {
      if (decoration.type === "tree") {
        this.add
          .image(decoration.x, decoration.y, "tree")
          .setOrigin(0.5, 0.72)
          .setDepth(decoration.y + 28);
      } else if (decoration.type === "flowers") {
        this.add
          .image(decoration.x - 16, decoration.y - 16, TILE.flowers)
          .setOrigin(0)
          .setDepth(4);
      } else if (decoration.type === "lamp") {
        this.add
          .image(decoration.x, decoration.y, "lamp")
          .setOrigin(0.5, 0.85)
          .setDepth(decoration.y + 18);
      }
    }
  }

  private drawInteractables(): void {
    for (const item of getLayer("interactables")) {
      if (item.type === "fountain") this.drawFountain(item);
      if (item.type === "notice_board") this.drawNoticeBoard(item);
      if (item.type === "bench") this.drawBench(item);
    }
  }

  private drawFountain(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 28);
    graphics.fillStyle(0x315f68, 1);
    graphics.fillRect(item.x - 39, item.y + 8, 78, 18);
    graphics.fillStyle(0xa8d7d2, 1);
    graphics.fillRect(item.x - 34, item.y, 68, 20);
    graphics.fillStyle(0x4ca6c3, 1);
    graphics.fillRect(item.x - 28, item.y + 3, 56, 12);
    graphics.fillStyle(0xe0f7ea, 1);
    graphics.fillRect(item.x - 4, item.y - 18, 8, 22);
    graphics.fillStyle(0x7acadd, 1);
    graphics.fillRect(item.x - 11, item.y - 12, 22, 5);
  }

  private drawNoticeBoard(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 24);
    graphics.fillStyle(0x553728, 1);
    graphics.fillRect(item.x - 21, item.y - 25, 42, 31);
    graphics.fillStyle(0xdeb874, 1);
    graphics.fillRect(item.x - 17, item.y - 21, 34, 23);
    graphics.fillStyle(0xf3e5bd, 1);
    graphics.fillRect(item.x - 10, item.y - 16, 14, 11);
    graphics.fillStyle(0x553728, 1);
    graphics.fillRect(item.x - 15, item.y + 4, 6, 22);
    graphics.fillRect(item.x + 9, item.y + 4, 6, 22);
  }

  private drawBench(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 18);
    graphics.fillStyle(0x66412f, 1);
    graphics.fillRect(item.x - 24, item.y - 8, 48, 8);
    graphics.fillRect(item.x - 24, item.y + 5, 48, 7);
    graphics.fillStyle(0x3e332a, 1);
    graphics.fillRect(item.x - 17, item.y + 11, 5, 10);
    graphics.fillRect(item.x + 12, item.y + 11, 5, 10);
  }

  private drawAgents(): void {
    for (const spawn of getLayer("spawns")) {
      const id = getProperty(spawn, "agent_id", spawn.name);
      const color = parseColor(getProperty(spawn, "color"), 0x6487d6);
      const container = this.add
        .container(spawn.x, spawn.y)
        .setDepth(spawn.y + 40)
        .setSize(24, 32)
        .setInteractive();
      const shadow = this.add.rectangle(0, 13, 22, 7, 0x183328, 0.35);
      const leftLeg = this.add.rectangle(-5, 10, 6, 9, 0x41372f);
      const rightLeg = this.add.rectangle(5, 10, 6, 9, 0x41372f);
      const body = this.add.rectangle(0, 1, 20, 20, color);
      const neck = this.add.rectangle(0, -9, 8, 5, 0xe8ba91);
      const head = this.add.rectangle(0, -17, 17, 15, 0xf1c9a1);
      const hair = this.add.rectangle(
        0,
        -23,
        19,
        7,
        id === "Sujin" ? 0x4b2f2c : 0x34302d,
      );
      const fringe = this.add.rectangle(
        -6,
        -19,
        5,
        6,
        id === "Sujin" ? 0x4b2f2c : 0x34302d,
      );
      const eyes = this.add.rectangle(0, -16, 10, 2, 0x3d3835);
      const bubble = this.add
        .text(13, -38, id === "Jiho" ? "☕" : "📚", {
          fontFamily: PIXEL_FONT,
          fontSize: "12px",
          backgroundColor: "#fffbed",
          padding: { x: 4, y: 3 },
        })
        .setOrigin(0.5)
        .setVisible(false)
        .setResolution(1);
      const nameplate = this.add
        .text(0, 28, spawn.name, {
          fontFamily: PIXEL_FONT,
          fontSize: "9px",
          fontStyle: "bold",
          color: "#fffbe8",
          backgroundColor: "#263e32",
          padding: { x: 4, y: 2 },
        })
        .setOrigin(0.5)
        .setResolution(1);
      container.add([
        shadow,
        leftLeg,
        rightLeg,
        body,
        neck,
        head,
        hair,
        fringe,
        eyes,
        bubble,
        nameplate,
      ]);
      container.on("pointerdown", () => this.followAgent(id));
      this.agentViews.set(id, {
        container,
        body,
        leftLeg,
        rightLeg,
        bubble,
        nameplate,
        lastX: spawn.x,
        lastY: spawn.y,
      });
    }
  }

  private applyAgentStates(states: Record<string, SpatialAgentState>): void {
    for (const [id, state] of Object.entries(states)) {
      const view =
        this.agentViews.get(id) ??
        this.agentViews.get(state.name.split(" ")[0]);
      if (!view) continue;
      const dx = state.position.x - view.lastX;
      const dy = state.position.y - view.lastY;
      view.lastX = state.position.x;
      view.lastY = state.position.y;
      view.body.setScale(Math.abs(dx) > Math.abs(dy) ? 0.9 : 1, 1);
      view.leftLeg.y = dx + dy === 0 ? 10 : 8;
      view.rightLeg.y = dx + dy === 0 ? 10 : 12;
      view.bubble
        .setText(this.actionEmoji(state.current_action))
        .setVisible(true);
      view.nameplate.setText(state.name);
      view.container.setDepth(state.position.y + 40);
      this.tweens.killTweensOf(view.container);
      this.tweens.add({
        targets: view.container,
        x: state.position.x,
        y: state.position.y,
        duration: 780,
        ease: "Linear",
      });
    }
  }

  private actionEmoji(action: string): string {
    if (action.includes("cafe") || action.includes("Honey")) return "☕";
    if (action.includes("library") || action.includes("Story")) return "📚";
    if (action.includes("market") || action.includes("Willow")) return "🧺";
    if (action.includes("park") || action.includes("Moonflower")) return "🌿";
    if (action.includes("moving")) return "…";
    return "💭";
  }

  private configureCamera(): void {
    const camera = this.cameras.main;
    camera.setZoom(this.scale.width < 720 ? 1.15 : 1.65).setRoundPixels(true);
    this.cursors = this.input.keyboard?.createCursorKeys();
    this.input.on(
      "wheel",
      (
        _pointer: Phaser.Input.Pointer,
        _objects: Phaser.GameObjects.GameObject[],
        _dx: number,
        dy: number,
      ) => {
        camera.setZoom(Phaser.Math.Clamp(camera.zoom - dy * 0.001, 1, 2.4));
      },
    );
    this.input.on("pointerdown", (pointer: Phaser.Input.Pointer) => {
      this.dragOrigin = new Phaser.Math.Vector2(pointer.x, pointer.y);
    });
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
      if (!pointer.isDown || !this.dragOrigin) return;
      const dx = pointer.x - this.dragOrigin.x;
      const dy = pointer.y - this.dragOrigin.y;
      if (Math.abs(dx) + Math.abs(dy) < 3) return;
      this.stopFollowing();
      camera.scrollX -= dx / camera.zoom;
      camera.scrollY -= dy / camera.zoom;
      this.dragOrigin.set(pointer.x, pointer.y);
    });
    this.followAgent(this.followedAgentId);
  }

  private followAgent(id: string): void {
    const view = this.agentViews.get(id);
    if (!view) return;
    this.followedAgentId = id;
    this.cameras.main.startFollow(view.container, true, 0.12, 0.12);
    for (const [agentId, candidate] of this.agentViews)
      candidate.nameplate.setBackgroundColor(
        agentId === id ? "#a24e53" : "#263e32",
      );
  }

  private stopFollowing(): void {
    this.cameras.main.stopFollow();
  }

  private drawWorldTitle(): void {
    this.add
      .text(34, 36, "BRIAR COVE", {
        fontFamily: PIXEL_FONT,
        fontSize: "14px",
        fontStyle: "bold",
        color: "#fff7d1",
        backgroundColor: "#1d3b2c",
        padding: { x: 9, y: 6 },
      })
      .setDepth(2000)
      .setResolution(1);
  }
}
