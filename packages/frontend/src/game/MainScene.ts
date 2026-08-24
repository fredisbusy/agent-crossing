import Phaser from "phaser";
import {
  getLayer,
  getProperty,
  parseColor,
  townMap,
  type TiledObject,
} from "../map/tiled";

const FONT_FAMILY = '"Nunito", "Apple SD Gothic Neo", sans-serif';
const WORLD_WIDTH = townMap.width * townMap.tilewidth;
const WORLD_HEIGHT = townMap.height * townMap.tileheight;

export class MainScene extends Phaser.Scene {
  constructor() {
    super("MainScene");
  }

  create() {
    this.cameras.main.setBackgroundColor("#a9cf91");
    this.cameras.main.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);
    this.physics.world.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);

    this.drawGround();
    this.drawPaths();
    this.drawLocations();
    this.drawDecorations();
    this.drawInteractables();
    this.drawAgents();
    this.addAtmosphere();

    this.scale.on("resize", () => this.fitCamera());
    this.fitCamera();
  }

  private fitCamera(): void {
    const camera = this.cameras.main;
    const zoom = Math.min(
      camera.width / WORLD_WIDTH,
      camera.height / WORLD_HEIGHT,
    );
    camera.setZoom(zoom);
    camera.centerOn(WORLD_WIDTH / 2, WORLD_HEIGHT / 2);
  }

  private drawGround(): void {
    const graphics = this.add.graphics();
    graphics.fillStyle(0xb8d89a, 1);
    graphics.fillRect(0, 0, WORLD_WIDTH, WORLD_HEIGHT);

    for (let y = 16; y < WORLD_HEIGHT; y += 32) {
      for (let x = 16; x < WORLD_WIDTH; x += 32) {
        const tone = (x / 32 + y / 32) % 3 === 0 ? 0xaed08f : 0xc0dda3;
        graphics.fillStyle(tone, 0.18);
        graphics.fillCircle(x + ((y / 32) % 2) * 5, y, 2);
      }
    }

    graphics.lineStyle(3, 0x7cae79, 0.4);
    graphics.strokeRoundedRect(18, 18, WORLD_WIDTH - 36, WORLD_HEIGHT - 36, 30);
  }

  private drawPaths(): void {
    const graphics = this.add.graphics();
    for (const path of getLayer("paths")) {
      if (!path.polyline || path.polyline.length < 2) {
        continue;
      }
      const points = path.polyline.map(
        (point) => new Phaser.Math.Vector2(path.x + point.x, path.y + point.y),
      );
      graphics.lineStyle(50, 0x8d785f, 0.14);
      graphics.strokePoints(points, false, false);
      graphics.lineStyle(42, 0xead8b6, 1);
      graphics.strokePoints(points, false, false);
      graphics.lineStyle(2, 0xf6ead0, 0.8);
      graphics.strokePoints(points, false, false);
    }
  }

  private drawLocations(): void {
    for (const location of getLayer("locations")) {
      const kind = getProperty(location, "kind", "building");
      if (kind === "plaza") {
        this.drawPlaza(location);
      } else if (kind === "park") {
        this.drawPark(location);
      } else {
        this.drawBuilding(location, kind);
      }
    }
  }

  private drawPlaza(location: TiledObject): void {
    const width = location.width ?? 0;
    const height = location.height ?? 0;
    const graphics = this.add.graphics();
    graphics.fillStyle(0x7b6d5f, 0.15);
    graphics.fillRoundedRect(
      location.x + 8,
      location.y + 12,
      width,
      height,
      36,
    );
    graphics.fillStyle(0xefd9ae, 1);
    graphics.fillRoundedRect(location.x, location.y, width, height, 36);
    graphics.lineStyle(3, 0xf9e8c8, 0.9);
    graphics.strokeRoundedRect(location.x, location.y, width, height, 36);

    for (let y = location.y + 26; y < location.y + height - 16; y += 26) {
      for (let x = location.x + 25; x < location.x + width - 16; x += 28) {
        graphics.fillStyle(0xd9bd8c, 0.42);
        graphics.fillCircle(x + ((y / 26) % 2) * 8, y, 2.2);
      }
    }
    this.addLocationLabel(location, "Town Square", "the heart of Briar Cove");
  }

  private drawPark(location: TiledObject): void {
    const width = location.width ?? 0;
    const height = location.height ?? 0;
    const graphics = this.add.graphics();
    graphics.fillStyle(0x6b9f70, 0.22);
    graphics.fillRoundedRect(location.x + 7, location.y + 9, width, height, 42);
    graphics.fillStyle(0x9bc78d, 1);
    graphics.fillRoundedRect(location.x, location.y, width, height, 42);
    graphics.lineStyle(3, 0xd2e7b5, 0.75);
    graphics.strokeRoundedRect(location.x, location.y, width, height, 42);

    graphics.fillStyle(0x6facc5, 0.32);
    graphics.fillEllipse(location.x + 238, location.y + 127, 164, 126);
    graphics.fillStyle(0x87c8dc, 1);
    graphics.fillEllipse(location.x + 232, location.y + 120, 154, 116);
    graphics.lineStyle(3, 0xc6edf0, 0.85);
    graphics.strokeEllipse(location.x + 232, location.y + 120, 140, 100);
    this.addLocationLabel(
      location,
      "Moonflower Park",
      "quiet paths & willow shade",
    );
  }

  private drawBuilding(location: TiledObject, kind: string): void {
    const width = location.width ?? 0;
    const height = location.height ?? 0;
    const baseColor = parseColor(getProperty(location, "color"), 0xd5a179);
    const graphics = this.add.graphics();
    const bodyX = location.x + 16;
    const bodyY = location.y + 45;
    const bodyWidth = width - 32;
    const bodyHeight = height - 62;

    graphics.fillStyle(0x3e5140, 0.16);
    graphics.fillRoundedRect(bodyX + 8, bodyY + 12, bodyWidth, bodyHeight, 18);
    graphics.fillStyle(baseColor, 1);
    graphics.fillRoundedRect(bodyX, bodyY, bodyWidth, bodyHeight, 18);
    graphics.fillStyle(0x6a5147, 1);
    graphics.fillTriangle(
      location.x + 6,
      bodyY + 16,
      location.x + width - 6,
      bodyY + 16,
      location.x + width / 2,
      location.y + 4,
    );
    graphics.fillStyle(0x80645a, 1);
    graphics.fillTriangle(
      location.x + 18,
      bodyY + 13,
      location.x + width - 18,
      bodyY + 13,
      location.x + width / 2,
      location.y + 16,
    );

    const doorX = location.x + width / 2 - 15;
    graphics.fillStyle(0x5c463f, 1);
    graphics.fillRoundedRect(doorX, location.y + height - 70, 30, 54, 8);
    graphics.fillStyle(0xf7d98a, 1);
    graphics.fillCircle(doorX + 23, location.y + height - 43, 2.5);

    const windowY = location.y + height - 78;
    for (const windowX of [location.x + 42, location.x + width - 66]) {
      graphics.fillStyle(0xf6e7b6, 1);
      graphics.fillRoundedRect(windowX, windowY, 28, 25, 6);
      graphics.lineStyle(2, 0xffffff, 0.55);
      graphics.lineBetween(
        windowX + 14,
        windowY + 2,
        windowX + 14,
        windowY + 23,
      );
    }

    if (kind === "cafe" || kind === "market") {
      graphics.fillStyle(0xf7ede0, 1);
      graphics.fillRoundedRect(location.x + 48, bodyY + 20, width - 96, 27, 8);
      for (let x = location.x + 52; x < location.x + width - 50; x += 28) {
        graphics.fillStyle(kind === "cafe" ? 0xc96e6e : 0x6b9c83, 1);
        graphics.fillTriangle(
          x,
          bodyY + 45,
          x + 14,
          bodyY + 20,
          x + 28,
          bodyY + 45,
        );
      }
    }

    const subtitle =
      kind === "cafe"
        ? "coffee, gossip & warm bread"
        : kind === "library"
          ? "stories, study & reflection"
          : kind === "market"
            ? "produce, errands & exchange"
            : "a cozy private home";
    this.addLocationLabel(location, location.name, subtitle);
  }

  private addLocationLabel(
    location: TiledObject,
    title: string,
    subtitle: string,
  ): void {
    const width = location.width ?? 0;
    const titleText = this.add
      .text(location.x + width / 2, location.y - 17, title, {
        fontFamily: FONT_FAMILY,
        fontSize: "15px",
        fontStyle: "bold",
        color: "#304334",
        backgroundColor: "rgba(250, 248, 236, 0.92)",
        padding: { x: 10, y: 5 },
      })
      .setOrigin(0.5)
      .setDepth(20);
    titleText.setShadow(0, 2, "rgba(34, 54, 37, 0.14)", 3);
    this.add
      .text(
        location.x + width / 2,
        location.y + (location.height ?? 0) + 15,
        subtitle,
        {
          fontFamily: FONT_FAMILY,
          fontSize: "10px",
          color: "#546555",
        },
      )
      .setOrigin(0.5)
      .setDepth(20);
  }

  private drawDecorations(): void {
    for (const decoration of getLayer("decorations")) {
      if (decoration.type === "tree") {
        this.drawTree(decoration.x, decoration.y);
      } else if (decoration.type === "flowers") {
        this.drawFlowers(decoration.x, decoration.y);
      } else if (decoration.type === "lamp") {
        this.drawLamp(decoration.x, decoration.y);
      }
    }
  }

  private drawTree(x: number, y: number): void {
    const graphics = this.add.graphics();
    graphics.fillStyle(0x345c48, 0.14);
    graphics.fillEllipse(x + 4, y + 28, 50, 16);
    graphics.fillStyle(0x806047, 1);
    graphics.fillRoundedRect(x - 5, y + 7, 10, 28, 5);
    graphics.fillStyle(0x5c9667, 1);
    graphics.fillCircle(x - 11, y, 20);
    graphics.fillStyle(0x77ac76, 1);
    graphics.fillCircle(x + 10, y - 5, 23);
    graphics.fillStyle(0x94c486, 0.95);
    graphics.fillCircle(x + 1, y - 19, 19);
  }

  private drawFlowers(x: number, y: number): void {
    const graphics = this.add.graphics();
    const colors = [0xf0a3b6, 0xf5d06f, 0xa693cf, 0xf6f0dc];
    for (let index = 0; index < 8; index += 1) {
      const angle = (Math.PI * 2 * index) / 8;
      const flowerX = x + Math.cos(angle) * (10 + (index % 2) * 7);
      const flowerY = y + Math.sin(angle) * 8;
      graphics.fillStyle(colors[index % colors.length], 1);
      graphics.fillCircle(flowerX, flowerY, 3.5);
      graphics.fillStyle(0xfff0a8, 1);
      graphics.fillCircle(flowerX, flowerY, 1.2);
    }
  }

  private drawLamp(x: number, y: number): void {
    const graphics = this.add.graphics();
    graphics.fillStyle(0x435149, 1);
    graphics.fillRoundedRect(x - 2, y - 4, 4, 27, 2);
    graphics.fillStyle(0xffe89a, 0.22);
    graphics.fillCircle(x, y - 6, 14);
    graphics.fillStyle(0xffe59a, 1);
    graphics.fillCircle(x, y - 7, 5);
  }

  private drawInteractables(): void {
    for (const item of getLayer("interactables")) {
      if (item.type === "fountain") {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x6f8e91, 0.22);
        graphics.fillEllipse(item.x + 3, item.y + 9, 68, 35);
        graphics.fillStyle(0xb9d8d5, 1);
        graphics.fillEllipse(item.x, item.y, 66, 34);
        graphics.fillStyle(0x78b8c8, 1);
        graphics.fillEllipse(item.x, item.y - 2, 52, 23);
        graphics.fillStyle(0xe3f4ed, 0.85);
        graphics.fillCircle(item.x, item.y - 9, 7);
      } else if (item.type === "notice_board") {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x70503f, 1);
        graphics.fillRoundedRect(item.x - 17, item.y - 21, 34, 27, 4);
        graphics.fillStyle(0xf3deaa, 1);
        graphics.fillRoundedRect(item.x - 12, item.y - 16, 24, 17, 2);
        graphics.fillStyle(0x70503f, 1);
        graphics.fillRect(item.x - 10, item.y + 5, 4, 16);
        graphics.fillRect(item.x + 6, item.y + 5, 4, 16);
      } else if (item.type === "bench") {
        const graphics = this.add.graphics();
        graphics.fillStyle(0x725545, 1);
        graphics.fillRoundedRect(item.x - 20, item.y - 7, 40, 8, 3);
        graphics.fillRoundedRect(item.x - 20, item.y + 4, 40, 7, 3);
        graphics.fillRect(item.x - 15, item.y + 10, 4, 9);
        graphics.fillRect(item.x + 11, item.y + 10, 4, 9);
      }
    }
  }

  private drawAgents(): void {
    for (const spawn of getLayer("spawns")) {
      const color = parseColor(getProperty(spawn, "color"), 0x6b8fd6);
      const container = this.add.container(spawn.x, spawn.y).setDepth(50);
      const shadow = this.add.ellipse(0, 15, 34, 13, 0x263d32, 0.18);
      const body = this.add.circle(0, 0, 16, color);
      body.setStrokeStyle(3, 0xf9f3df, 1);
      const face = this.add.circle(0, -5, 9, 0xf4d4b2);
      const hair = this.add.arc(0, -8, 9, 185, 355, false, 0x4d3d3a);
      const eyeLeft = this.add.circle(-3, -4, 1.2, 0x343238);
      const eyeRight = this.add.circle(3, -4, 1.2, 0x343238);
      const name = this.add
        .text(0, 29, spawn.name, {
          fontFamily: FONT_FAMILY,
          fontSize: "12px",
          fontStyle: "bold",
          color: "#34493a",
          backgroundColor: "rgba(255,255,245,0.9)",
          padding: { x: 7, y: 3 },
        })
        .setOrigin(0.5);
      const bubble = this.add
        .text(17, -25, spawn.name === "Jiho" ? "☕" : "📚", {
          fontFamily: FONT_FAMILY,
          fontSize: "14px",
          backgroundColor: "rgba(255,255,255,0.94)",
          padding: { x: 6, y: 4 },
        })
        .setOrigin(0.5);
      container.add([
        shadow,
        body,
        face,
        hair,
        eyeLeft,
        eyeRight,
        name,
        bubble,
      ]);

      this.tweens.add({
        targets: container,
        y: spawn.y - 4,
        duration: 1300 + spawn.id * 7,
        yoyo: true,
        repeat: -1,
        ease: "Sine.inOut",
      });
    }
  }

  private addAtmosphere(): void {
    for (let index = 0; index < 8; index += 1) {
      const mote = this.add.circle(
        120 + index * 143,
        90 + (index % 4) * 180,
        2 + (index % 2),
        index % 3 === 0 ? 0xfff4bd : 0xffffff,
        0.65,
      );
      this.tweens.add({
        targets: mote,
        x: mote.x + 28,
        y: mote.y - 18,
        alpha: 0.15,
        duration: 2600 + index * 220,
        yoyo: true,
        repeat: -1,
        ease: "Sine.inOut",
      });
    }
  }
}
