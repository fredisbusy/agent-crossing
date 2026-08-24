import Phaser from "phaser";
import { useGameStore } from "../stores/game.store";
import { createPixelTextures, TILE, TILE_SIZE } from "./pixelTextures";
import { agentBubbleLabel } from "./agentBubble";
import { GameTextOverlayController } from "./gameText";

const ROOM_COLUMNS = 20;
const ROOM_ROWS = 14;
const ROOM_WIDTH = ROOM_COLUMNS * TILE_SIZE;
const ROOM_HEIGHT = ROOM_ROWS * TILE_SIZE;

interface InteriorData {
  name: string;
  kind: string;
  color: string;
}

export class InteriorScene extends Phaser.Scene {
  private interior: InteriorData = {
    name: "브라이어 코브의 집",
    kind: "home",
    color: "#d58c68",
  };
  private residentLayer?: Phaser.GameObjects.Container;
  private unsubscribeStore?: () => void;
  private textOverlay!: GameTextOverlayController;

  constructor() {
    super("InteriorScene");
  }

  init(data: InteriorData): void {
    this.interior = data;
  }

  create(): void {
    createPixelTextures(this);
    this.textOverlay = new GameTextOverlayController(
      this,
      `interior:${this.interior.name}`,
    );
    useGameStore.getState().setSceneContext({
      kind: "interior",
      name: this.interior.name,
    });
    this.cameras.main.setBackgroundColor("#13271e");
    this.drawRoomShell();
    this.drawInteriorByKind();
    this.drawResidents();
    this.drawExit();
    this.drawRoomHud();
    this.fitCamera();

    const unsubscribeStore = useGameStore.subscribe((state, previousState) => {
      if (state.agents !== previousState.agents) {
        this.drawResidents();
      }
      if (state.followRequestId !== previousState.followRequestId) {
        this.scene.start("MainScene");
      }
    });
    this.unsubscribeStore = unsubscribeStore;

    const handleResize = () => this.fitCamera();
    this.scale.on("resize", handleResize);
    const cleanup = () => {
      this.scale.off("resize", handleResize);
      unsubscribeStore();
      this.textOverlay.destroy();
      if (this.unsubscribeStore === unsubscribeStore) {
        this.unsubscribeStore = undefined;
      }
    };
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, cleanup);
    this.events.once(Phaser.Scenes.Events.DESTROY, cleanup);
    this.input.keyboard?.on("keydown-ESC", () => this.exitInterior());
    this.input.keyboard?.on("keydown-E", () => this.exitInterior());
  }

  update(): void {
    this.textOverlay.sync();
  }

  private drawRoomShell(): void {
    const floorTexture =
      this.interior.kind === "market" ? TILE.stoneFloor : TILE.woodFloor;
    for (let y = 0; y < ROOM_ROWS; y += 1) {
      for (let x = 0; x < ROOM_COLUMNS; x += 1) {
        const isWall = y < 2 || x === 0 || x === ROOM_COLUMNS - 1;
        this.add
          .image(
            x * TILE_SIZE,
            y * TILE_SIZE,
            isWall ? TILE.wall : floorTexture,
          )
          .setOrigin(0)
          .setDepth(0);
      }
    }

    const trim = this.add.graphics().setDepth(2);
    trim.fillStyle(0x56382c, 1);
    trim.fillRect(0, 62, ROOM_WIDTH, 7);
    trim.fillRect(0, ROOM_HEIGHT - 12, ROOM_WIDTH, 12);
    trim.fillRect(0, 0, 9, ROOM_HEIGHT);
    trim.fillRect(ROOM_WIDTH - 9, 0, 9, ROOM_HEIGHT);
    trim.lineStyle(5, 0xead49a, 1);
    trim.strokeRect(3, 3, ROOM_WIDTH - 6, ROOM_HEIGHT - 6);
  }

  private drawInteriorByKind(): void {
    if (this.interior.kind === "cafe") {
      this.drawCafe();
    } else if (this.interior.kind === "library") {
      this.drawLibrary();
    } else if (this.interior.kind === "market") {
      this.drawMarket();
    } else {
      this.drawHome();
    }
  }

  private drawCafe(): void {
    this.drawCounter(86, 100, 190, "COFFEE & BREAD");
    this.drawShelf(38, 76, 36, 120, [0xd75b48, 0x68a989, 0xe1bc54]);
    this.drawPlant(575, 98);
    this.drawTableSet(390, 150);
    this.drawTableSet(500, 245);
    this.drawTableSet(330, 302);
    this.drawRug(250, 218, 106, 76, 0x9b5350);
  }

  private drawLibrary(): void {
    this.drawShelf(42, 82, 58, 250, [0xa44943, 0x557bb2, 0xd6a44e, 0x6b9e68]);
    this.drawShelf(540, 82, 58, 250, [0x557bb2, 0xd6a44e, 0x9d5a82, 0x6b9e68]);
    this.drawShelf(155, 82, 300, 42, [0x6b9e68, 0xa44943, 0x557bb2]);
    this.drawLongTable(245, 218);
    this.drawLongTable(395, 310);
    this.drawPlant(118, 365);
  }

  private drawMarket(): void {
    this.drawCounter(66, 92, 505, "WILLOW MARKET");
    this.drawProduceStall(110, 185, [0xe55d45, 0xe3b94c]);
    this.drawProduceStall(270, 185, [0x68a354, 0xe9d777]);
    this.drawProduceStall(430, 185, [0xd98054, 0x8bb65e]);
    this.drawShelf(75, 330, 470, 46, [0xd5aa55, 0x6d99b5, 0xd77d6f]);
  }

  private drawHome(): void {
    this.drawRug(220, 190, 200, 130, 0x71966a);
    this.drawBed(62, 95);
    this.drawShelf(490, 85, 80, 110, [0xd7b95d, 0x6f96b5, 0xcc7569]);
    this.drawLongTable(410, 285);
    this.drawPlant(555, 355);
    const kitchen = this.add.graphics().setDepth(80);
    kitchen.fillStyle(0x496d72, 1);
    kitchen.fillRect(62, 334, 185, 55);
    kitchen.fillStyle(0xd9d3b5, 1);
    kitchen.fillRect(67, 338, 175, 10);
    kitchen.fillStyle(0x263d42, 1);
    kitchen.fillRect(92, 352, 35, 24);
    kitchen.fillStyle(0xa8d8df, 1);
    kitchen.fillRect(98, 357, 23, 5);
  }

  private drawCounter(
    x: number,
    y: number,
    width: number,
    label: string,
  ): void {
    const graphics = this.add.graphics().setDepth(y + 60);
    graphics.fillStyle(0x4e3227, 1);
    graphics.fillRect(x, y, width, 55);
    graphics.fillStyle(0x8d5b3c, 1);
    graphics.fillRect(x + 5, y + 8, width - 10, 42);
    graphics.fillStyle(0xd4a064, 1);
    graphics.fillRect(x - 6, y - 7, width + 12, 13);
    this.textOverlay.add({
      id: `counter:${label}`,
      text: label,
      x: x + width / 2,
      y: y + 21,
      tone: "location",
    });
  }

  private drawShelf(
    x: number,
    y: number,
    width: number,
    height: number,
    colors: number[],
  ): void {
    const graphics = this.add.graphics().setDepth(y + height);
    graphics.fillStyle(0x4d3328, 1);
    graphics.fillRect(x, y, width, height);
    graphics.fillStyle(0x805438, 1);
    graphics.fillRect(x + 5, y + 5, width - 10, height - 10);
    for (let shelfY = y + 12; shelfY < y + height - 12; shelfY += 20) {
      for (let itemX = x + 10; itemX < x + width - 10; itemX += 10) {
        graphics.fillStyle(colors[(itemX + shelfY) % colors.length], 1);
        graphics.fillRect(itemX, shelfY, 7, 13);
      }
      graphics.fillStyle(0x4d3328, 1);
      graphics.fillRect(x + 5, shelfY + 14, width - 10, 4);
    }
  }

  private drawTableSet(x: number, y: number): void {
    const graphics = this.add.graphics().setDepth(y + 38);
    graphics.fillStyle(0x51362b, 1);
    graphics.fillRect(x - 31, y - 23, 62, 47);
    graphics.fillStyle(0xb77d4d, 1);
    graphics.fillRect(x - 26, y - 18, 52, 37);
    graphics.fillStyle(0x744b37, 1);
    graphics.fillRect(x - 50, y - 16, 13, 32);
    graphics.fillRect(x + 37, y - 16, 13, 32);
    graphics.fillStyle(0xeed8a3, 1);
    graphics.fillRect(x - 8, y - 7, 16, 12);
  }

  private drawLongTable(x: number, y: number): void {
    const graphics = this.add.graphics().setDepth(y + 35);
    graphics.fillStyle(0x57392d, 1);
    graphics.fillRect(x - 70, y - 20, 140, 42);
    graphics.fillStyle(0xa66f48, 1);
    graphics.fillRect(x - 64, y - 15, 128, 31);
    graphics.fillStyle(0x6d4935, 1);
    for (const chairX of [x - 54, x, x + 54]) {
      graphics.fillRect(chairX - 9, y - 39, 18, 13);
      graphics.fillRect(chairX - 9, y + 28, 18, 13);
    }
  }

  private drawProduceStall(
    x: number,
    y: number,
    colors: [number, number],
  ): void {
    const graphics = this.add.graphics().setDepth(y + 85);
    graphics.fillStyle(0x50382d, 1);
    graphics.fillRect(x, y, 105, 76);
    graphics.fillStyle(0xb77a46, 1);
    graphics.fillRect(x + 6, y + 6, 93, 64);
    for (let row = 0; row < 3; row += 1) {
      for (let column = 0; column < 5; column += 1) {
        graphics.fillStyle(colors[(row + column) % 2], 1);
        graphics.fillRect(x + 13 + column * 17, y + 12 + row * 17, 10, 10);
      }
    }
  }

  private drawBed(x: number, y: number): void {
    const graphics = this.add.graphics().setDepth(y + 120);
    graphics.fillStyle(0x52362d, 1);
    graphics.fillRect(x, y, 115, 135);
    graphics.fillStyle(0xe8dfbf, 1);
    graphics.fillRect(x + 7, y + 7, 101, 121);
    graphics.fillStyle(0x83a6c8, 1);
    graphics.fillRect(x + 7, y + 48, 101, 80);
    graphics.fillStyle(0xbcd1dd, 1);
    graphics.fillRect(x + 15, y + 15, 40, 25);
  }

  private drawRug(
    x: number,
    y: number,
    width: number,
    height: number,
    color: number,
  ): void {
    const graphics = this.add.graphics().setDepth(3);
    graphics.fillStyle(0x5f4134, 1);
    graphics.fillRect(x - 5, y - 5, width + 10, height + 10);
    graphics.fillStyle(color, 1);
    graphics.fillRect(x, y, width, height);
    graphics.lineStyle(4, 0xe2bd77, 1);
    graphics.strokeRect(x + 7, y + 7, width - 14, height - 14);
  }

  private drawPlant(x: number, y: number): void {
    const graphics = this.add.graphics().setDepth(y + 42);
    graphics.fillStyle(0x8b5739, 1);
    graphics.fillRect(x - 14, y + 20, 28, 24);
    graphics.fillStyle(0x37784a, 1);
    graphics.fillRect(x - 20, y, 17, 28);
    graphics.fillRect(x + 3, y - 7, 17, 35);
    graphics.fillStyle(0x61a55c, 1);
    graphics.fillRect(x - 7, y - 16, 15, 36);
  }

  private drawResidents(): void {
    this.residentLayer?.destroy(true);
    this.textOverlay.removeByPrefix("resident:");
    const residentLayer = this.add.container(0, 0);
    this.residentLayer = residentLayer;
    const residents = Object.values(useGameStore.getState().agents).filter(
      (agent) =>
        agent.destination?.split(" > ").at(-1) === this.interior.name &&
        (agent.current_action.startsWith("at:") ||
          agent.current_action.startsWith("arrived_at:")),
    );
    residents.forEach((agent, index) => {
      const x = 285 + index * 88;
      const y = 178 + (index % 2) * 90;
      const resident = this.add
        .container(x, y)
        .setSize(56, 72)
        .setDepth(y + 30)
        .setInteractive({ useHandCursor: true });
      const graphics = this.add.graphics();
      graphics.fillStyle(0x183328, 0.3);
      graphics.fillRect(-12, 20, 24, 6);
      graphics.fillStyle(
        agent.agent_id.toLocaleLowerCase().includes("sujin")
          ? 0xc95f7e
          : 0x587cd0,
        1,
      );
      graphics.fillRect(-10, 0, 20, 21);
      graphics.fillStyle(0xefc59e, 1);
      graphics.fillRect(-8, -15, 16, 15);
      graphics.fillStyle(0x3e322e, 1);
      graphics.fillRect(-9, -20, 18, 7);
      resident.add(graphics);
      resident.on("pointerdown", () =>
        useGameStore.getState().selectAgent(agent.agent_id),
      );
      residentLayer.add(resident);
      this.textOverlay.add({
        id: `resident:${agent.agent_id}:bubble`,
        text: agentBubbleLabel(agent),
        x: () => resident.x,
        y: () => resident.y - 34,
        tone: "bubble",
        anchor: "bottom",
        maxWidth: 300,
      });
      this.textOverlay.add({
        id: `resident:${agent.agent_id}:name`,
        text: agent.name,
        x: () => resident.x,
        y: () => resident.y + 31,
        tone: "nameplate",
        selected: () =>
          useGameStore.getState().selectedAgentId === agent.agent_id,
      });
    });
  }

  private drawExit(): void {
    const x = ROOM_WIDTH / 2;
    const y = ROOM_HEIGHT - 27;
    const graphics = this.add.graphics().setDepth(500);
    graphics.fillStyle(0x382820, 1);
    graphics.fillRect(x - 28, ROOM_HEIGHT - 66, 56, 66);
    graphics.fillStyle(0xd5ae68, 1);
    graphics.fillRect(x - 19, ROOM_HEIGHT - 10, 38, 7);
    this.textOverlay.add({
      id: "interior:exit",
      text: "▲  EXIT",
      x,
      y: y - 8,
      tone: "action",
    });
    const exitZone = this.add
      .zone(x, y - 8, 76, 34)
      .setDepth(502)
      .setInteractive({ useHandCursor: true });
    exitZone.on("pointerdown", () => this.exitInterior());
  }

  private drawRoomHud(): void {
    this.textOverlay.add({
      id: "interior:title",
      text: this.interior.name.toUpperCase(),
      x: 18,
      y: 18,
      tone: "title",
      anchor: "left-top",
    });
    this.textOverlay.add({
      id: "interior:leave-hint",
      text: "ESC / E  LEAVE",
      x: ROOM_WIDTH - 18,
      y: 18,
      tone: "location",
      anchor: "right-top",
    });
  }

  private fitCamera(): void {
    const camera = this.cameras.main;
    const zoom = Phaser.Math.Clamp(
      Math.min(
        this.scale.width / (ROOM_WIDTH + 140),
        this.scale.height / (ROOM_HEIGHT + 90),
      ),
      1,
      1.8,
    );
    camera
      .setZoom(zoom)
      .setRoundPixels(true)
      .centerOn(ROOM_WIDTH / 2, ROOM_HEIGHT / 2);
  }

  private exitInterior(): void {
    this.scene.start("MainScene");
  }
}
