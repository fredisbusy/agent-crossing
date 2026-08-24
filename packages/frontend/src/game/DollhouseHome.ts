import Phaser from "phaser";
import type { TiledObject } from "../map/tiled";
import { GAME_UI_FONT, makeCrispText } from "./gameText";
import { HOME_ROOMS, type HomeRoom } from "./homeInterior";

export interface DollhouseHomeView {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
  roomPositions: Readonly<Record<HomeRoom, Phaser.Math.Vector2>>;
}

export interface IndoorResidentView {
  container: Phaser.GameObjects.Container;
  bubble: Phaser.GameObjects.Text;
}

function roomPosition(
  x: number,
  y: number,
  width: number,
  height: number,
  room: HomeRoom,
): Phaser.Math.Vector2 {
  const definition = HOME_ROOMS.find((candidate) => candidate.id === room);
  if (!definition) {
    throw new Error(`Unknown home room: ${room}`);
  }
  return new Phaser.Math.Vector2(
    x + definition.residentX * width,
    y + definition.residentY * height,
  );
}

export function drawDollhouseHome(
  scene: Phaser.Scene,
  location: TiledObject,
  accentColor: number,
): DollhouseHomeView {
  const x = location.x + 10;
  const y = location.y + 12;
  const width = (location.width ?? 0) - 20;
  const height = (location.height ?? 0) - 22;
  const depth = location.y + (location.height ?? 0) - 8;
  const graphics = scene.add.graphics().setDepth(depth);

  graphics.fillStyle(0x173126, 0.35);
  graphics.fillRect(x + 7, y + 7, width, height);
  graphics.fillStyle(0x5a3c2e, 1);
  graphics.fillRect(x - 6, y - 6, width + 12, height + 12);

  for (const room of HOME_ROOMS) {
    const roomX = x + room.x * width;
    const roomY = y + room.y * height;
    const roomWidth = room.width * width;
    const roomHeight = room.height * height;
    const floorColor =
      room.id === "bathroom"
        ? 0xb9d7d2
        : room.id === "kitchen"
          ? 0xe6d29c
          : room.id === "bedroom"
            ? 0xd9c49d
            : 0xc99c6b;
    graphics.fillStyle(floorColor, 1);
    graphics.fillRect(roomX, roomY, roomWidth, roomHeight);
    graphics.lineStyle(1, 0x9d7652, 0.45);
    for (let plankY = roomY + 8; plankY < roomY + roomHeight; plankY += 9) {
      graphics.lineBetween(roomX, plankY, roomX + roomWidth, plankY);
    }
  }

  const splitX = x + width * 0.48;
  const splitY = y + height * 0.52;
  const bathX = x + width * 0.66;
  graphics.fillStyle(0x5a3c2e, 1);
  graphics.fillRect(splitX - 2, y, 5, height * 0.41);
  graphics.fillRect(splitX - 2, y + height * 0.46, 5, height * 0.12);
  graphics.fillRect(x, splitY - 2, width * 0.27, 5);
  graphics.fillRect(x + width * 0.38, splitY - 2, width * 0.25, 5);
  graphics.fillRect(x + width * 0.7, splitY - 2, width * 0.3, 5);
  graphics.fillRect(bathX - 2, splitY, 5, height * 0.18);
  graphics.fillRect(bathX - 2, y + height * 0.83, 5, height * 0.17);

  drawBed(graphics, x + 9, y + 10, width * 0.22, height * 0.31, accentColor);
  drawDesk(graphics, x + width * 0.29, y + 9, width * 0.15);
  drawKitchen(graphics, splitX + 8, y + 8, width * 0.46);
  drawCommonRoom(graphics, x + 10, splitY + 10, width * 0.55, height * 0.34);
  drawBathroom(graphics, bathX + 8, splitY + 8, width * 0.27, height * 0.34);

  graphics.lineStyle(5, 0xf0dca7, 1);
  graphics.strokeRect(x - 3, y - 3, width + 6, height + 6);
  graphics.lineStyle(3, accentColor, 1);
  graphics.strokeRect(x - 6, y - 6, width + 12, height + 12);

  for (const room of HOME_ROOMS) {
    makeCrispText(
      scene.add.text(
        x + room.x * width + 5,
        y + room.y * height + 4,
        room.label,
        {
          fontFamily: GAME_UI_FONT,
          fontSize: "6px",
          fontStyle: "bold",
          color: "#5a4334",
        },
      ),
    ).setDepth(depth + 1);
  }

  makeCrispText(
    scene.add.text(
      location.x + (location.width ?? 0) / 2,
      location.y - 4,
      location.name,
      {
        fontFamily: GAME_UI_FONT,
        fontSize: "9px",
        fontStyle: "bold",
        color: "#fff8d9",
        backgroundColor: "#253e31",
        padding: { x: 5, y: 3 },
      },
    ),
  )
    .setOrigin(0.5)
    .setDepth(depth + 20);

  return {
    name: location.name,
    x,
    y,
    width,
    height,
    depth,
    roomPositions: {
      bedroom: roomPosition(x, y, width, height, "bedroom"),
      kitchen: roomPosition(x, y, width, height, "kitchen"),
      common: roomPosition(x, y, width, height, "common"),
      bathroom: roomPosition(x, y, width, height, "bathroom"),
    },
  };
}

export function createIndoorResidentView(
  scene: Phaser.Scene,
  name: string,
  color: number,
): IndoorResidentView {
  const container = scene.add
    .container(0, 0)
    .setSize(44, 44)
    .setInteractive({ useHandCursor: true })
    .setVisible(false);
  const shadow = scene.add.rectangle(0, 9, 17, 5, 0x183328, 0.3);
  const body = scene.add.rectangle(0, 0, 14, 15, color);
  const head = scene.add.rectangle(0, -11, 12, 11, 0xefc59e);
  const hair = scene.add.rectangle(0, -16, 14, 5, 0x3e322e);
  const nameplate = makeCrispText(
    scene.add.text(0, 15, name, {
      fontFamily: GAME_UI_FONT,
      fontSize: "6px",
      fontStyle: "bold",
      color: "#fff3c1",
      backgroundColor: "#2a4334",
      padding: { x: 3, y: 1 },
    }),
  ).setOrigin(0.5, 0);
  const bubble = makeCrispText(
    scene.add.text(0, -27, "", {
      fontFamily: GAME_UI_FONT,
      fontSize: "6px",
      color: "#4a382d",
      backgroundColor: "#fff5d3",
      padding: { x: 3, y: 2 },
      wordWrap: { width: 118 },
      align: "center",
    }),
  ).setOrigin(0.5, 1);
  container.add([shadow, body, head, hair, nameplate, bubble]);
  return { container, bubble };
}

function drawBed(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
  color: number,
): void {
  graphics.fillStyle(0x654432, 1);
  graphics.fillRect(x, y, width, height);
  graphics.fillStyle(0xf0e5c5, 1);
  graphics.fillRect(x + 3, y + 3, width - 6, height - 6);
  graphics.fillStyle(color, 1);
  graphics.fillRect(x + 3, y + height * 0.42, width - 6, height * 0.52);
  graphics.fillStyle(0xffffff, 0.75);
  graphics.fillRect(x + 6, y + 6, width * 0.45, height * 0.25);
}

function drawDesk(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
): void {
  graphics.fillStyle(0x6c4934, 1);
  graphics.fillRect(x, y, width, 14);
  graphics.fillRect(x + 3, y + 12, 4, 15);
  graphics.fillRect(x + width - 7, y + 12, 4, 15);
  graphics.fillStyle(0x4f6f73, 1);
  graphics.fillRect(x + width * 0.28, y + 2, width * 0.45, 8);
}

function drawKitchen(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
): void {
  graphics.fillStyle(0x47666a, 1);
  graphics.fillRect(x, y, width, 20);
  graphics.fillStyle(0xe8dfbc, 1);
  graphics.fillRect(x + 2, y + 2, width - 4, 5);
  graphics.fillStyle(0x273e42, 1);
  graphics.fillRect(x + 8, y + 9, 18, 8);
  graphics.fillStyle(0xa8d8df, 1);
  graphics.fillRect(x + 11, y + 11, 12, 3);
  graphics.fillStyle(0x765441, 1);
  graphics.fillRect(x + width - 25, y + 29, 21, 23);
  graphics.fillStyle(0xf2d77d, 1);
  graphics.fillRect(x + width - 21, y + 33, 13, 4);
}

function drawCommonRoom(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  graphics.fillStyle(0x6b8f69, 1);
  graphics.fillRect(x, y, width, height);
  graphics.lineStyle(2, 0xe4c779, 1);
  graphics.strokeRect(x + 3, y + 3, width - 6, height - 6);
  graphics.fillStyle(0x724b35, 1);
  graphics.fillRect(x + width * 0.36, y + height * 0.3, width * 0.38, 16);
  graphics.fillStyle(0xa8794e, 1);
  graphics.fillRect(x + width * 0.39, y + height * 0.34, width * 0.32, 10);
  graphics.fillStyle(0x50382d, 1);
  graphics.fillRect(x + 3, y + 3, width * 0.16, height * 0.7);
  for (let shelf = y + 8; shelf < y + height * 0.65; shelf += 8) {
    graphics.fillStyle(0xd1a757, 1);
    graphics.fillRect(x + 6, shelf, width * 0.1, 5);
  }
}

function drawBathroom(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  graphics.fillStyle(0xf2f0df, 1);
  graphics.fillRect(x, y, width * 0.46, height * 0.62);
  graphics.fillStyle(0x8dc5ce, 1);
  graphics.fillRect(x + 4, y + 4, width * 0.34, height * 0.45);
  graphics.fillStyle(0xf5f2e2, 1);
  graphics.fillRect(x + width * 0.62, y + height * 0.48, width * 0.28, 14);
  graphics.fillStyle(0x8dc5ce, 1);
  graphics.fillRect(x + width * 0.68, y + height * 0.53, width * 0.16, 5);
}
