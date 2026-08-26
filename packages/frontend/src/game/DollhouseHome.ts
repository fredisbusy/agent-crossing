import Phaser from "phaser";
import { getProperty, townMap, type TiledObject } from "../map/tiled";
import { HOME_ROOMS, type HomeRoom } from "./homeInterior";

type HomeStyle = "standard" | "tinkerer" | "shuttle" | "host" | "archive";

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
  name: string;
  bubbleText: string;
  selected: boolean;
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
  drawHomeSignature(
    graphics,
    homeStyle(getProperty(location, "home_style", "standard")),
    x,
    y,
    width,
    height,
    accentColor,
  );
  drawHomeFrameWithDoor(
    graphics,
    x,
    y,
    width,
    height,
    accentColor,
    homeDoorCenterX(location, x, width),
  );

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

function homeDoorCenterX(
  location: TiledObject,
  fallbackX: number,
  width: number,
): number {
  const tileX = Number(getProperty(location, "entrance_tile_x"));
  if (!Number.isFinite(tileX)) return fallbackX + width / 2;
  return Phaser.Math.Clamp(
    tileX * townMap.tilewidth + townMap.tilewidth / 2,
    fallbackX + 20,
    fallbackX + width - 20,
  );
}

function drawHomeFrameWithDoor(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
  accentColor: number,
  doorCenterX: number,
): void {
  const outerLeft = x - 6;
  const outerRight = x + width + 6;
  const outerTop = y - 6;
  const outerBottom = y + height + 6;
  const innerLeft = x - 3;
  const innerRight = x + width + 3;
  const innerTop = y - 3;
  const innerBottom = y + height + 3;
  const doorWidth = 32;
  const doorLeft = doorCenterX - doorWidth / 2;
  const doorRight = doorCenterX + doorWidth / 2;

  graphics.lineStyle(5, 0xf0dca7, 1);
  graphics.lineBetween(innerLeft, innerTop, innerRight, innerTop);
  graphics.lineBetween(innerLeft, innerTop, innerLeft, innerBottom);
  graphics.lineBetween(innerRight, innerTop, innerRight, innerBottom);
  graphics.lineBetween(innerLeft, innerBottom, doorLeft, innerBottom);
  graphics.lineBetween(doorRight, innerBottom, innerRight, innerBottom);

  graphics.lineStyle(3, accentColor, 1);
  graphics.lineBetween(outerLeft, outerTop, outerRight, outerTop);
  graphics.lineBetween(outerLeft, outerTop, outerLeft, outerBottom);
  graphics.lineBetween(outerRight, outerTop, outerRight, outerBottom);
  graphics.lineBetween(outerLeft, outerBottom, doorLeft - 3, outerBottom);
  graphics.lineBetween(doorRight + 3, outerBottom, outerRight, outerBottom);

  const doorTop = y + height - 27;
  graphics.fillStyle(0x4b3428, 1);
  graphics.fillRect(doorLeft, doorTop, doorWidth, 33);
  graphics.lineStyle(3, 0xe7c77f, 1);
  graphics.strokeRect(doorLeft, doorTop, doorWidth, 33);
  graphics.fillStyle(0xf2d06f, 1);
  graphics.fillCircle(doorRight - 7, doorTop + 17, 2);

  graphics.fillStyle(0xe1c58f, 1);
  graphics.fillRect(doorLeft + 4, outerBottom + 1, doorWidth - 8, 7);
}

function homeStyle(value: string): HomeStyle {
  return ["tinkerer", "shuttle", "host", "archive"].includes(value)
    ? (value as HomeStyle)
    : "standard";
}

function drawHomeSignature(
  graphics: Phaser.GameObjects.Graphics,
  style: HomeStyle,
  x: number,
  y: number,
  width: number,
  height: number,
  accentColor: number,
): void {
  if (style === "tinkerer") {
    const benchX = x + width * 0.08;
    const benchY = y + height * 0.76;
    graphics.fillStyle(0x4f382b, 1);
    graphics.fillRect(benchX, benchY, width * 0.42, 11);
    graphics.fillRect(benchX + 5, benchY + 10, 4, 13);
    graphics.fillRect(benchX + width * 0.36, benchY + 10, 4, 13);
    graphics.fillStyle(0x75c7d8, 1);
    graphics.fillRect(benchX + 8, benchY - 6, 12, 6);
    graphics.fillStyle(0xe8bd55, 1);
    graphics.fillRect(benchX + 25, benchY - 8, 8, 8);
    graphics.lineStyle(2, accentColor, 1);
    graphics.lineBetween(benchX + 20, benchY - 3, benchX + 27, benchY - 4);
    graphics.lineBetween(benchX + 33, benchY - 4, benchX + 44, benchY + 1);
    return;
  }

  if (style === "shuttle") {
    const boardX = x + width * 0.31;
    const boardY = y + height * 0.08;
    graphics.fillStyle(0x274955, 1);
    graphics.fillRect(boardX, boardY, width * 0.13, height * 0.18);
    graphics.fillStyle(0xf4df8f, 1);
    graphics.fillRect(boardX + 4, boardY + 5, width * 0.04, 4);
    graphics.fillRect(boardX + 4, boardY + 13, width * 0.07, 4);
    const racketY = y + height * 0.76;
    graphics.lineStyle(3, 0xe9edf0, 1);
    graphics.strokeCircle(x + width * 0.18, racketY, 11);
    graphics.strokeCircle(x + width * 0.34, racketY, 11);
    graphics.lineStyle(4, accentColor, 1);
    graphics.lineBetween(
      x + width * 0.18 + 7,
      racketY + 8,
      x + width * 0.25,
      racketY + 23,
    );
    graphics.lineBetween(
      x + width * 0.34 - 7,
      racketY + 8,
      x + width * 0.28,
      racketY + 23,
    );
    return;
  }

  if (style === "host") {
    const tableX = x + width * 0.14;
    const tableY = y + height * 0.7;
    const tableWidth = width * 0.37;
    graphics.fillStyle(0x74472f, 1);
    graphics.fillRect(tableX, tableY, tableWidth, 22);
    graphics.fillStyle(0xc99758, 1);
    graphics.fillRect(tableX + 4, tableY + 4, tableWidth - 8, 14);
    graphics.fillStyle(0x49352b, 1);
    graphics.fillRect(tableX - 8, tableY + 5, 7, 13);
    graphics.fillRect(tableX + tableWidth + 1, tableY + 5, 7, 13);
    graphics.fillStyle(0xe7d8aa, 1);
    graphics.fillRect(tableX + tableWidth * 0.42, tableY + 7, 13, 8);
    graphics.fillStyle(accentColor, 1);
    graphics.fillRect(x + width * 0.87, y + height * 0.22, 5, 12);
    graphics.fillRect(x + width * 0.91, y + height * 0.2, 5, 14);
    return;
  }

  if (style === "archive") {
    const studioX = x + width * 0.08;
    const studioY = y + height * 0.7;
    graphics.fillStyle(0x44362e, 1);
    graphics.fillRect(studioX, studioY, width * 0.43, 10);
    graphics.fillStyle(0x6fc2d6, 1);
    graphics.fillRect(studioX + 6, studioY - 12, 18, 11);
    graphics.fillStyle(0xd98e92, 1);
    graphics.fillRect(studioX + 28, studioY - 10, 16, 9);
    graphics.fillStyle(0x2f3b49, 1);
    graphics.fillRect(studioX + 16, studioY + 10, 5, 12);
    graphics.fillStyle(0xf0e0ad, 1);
    for (let photo = 0; photo < 3; photo += 1) {
      graphics.fillRect(
        x + width * (0.3 + photo * 0.07),
        y + height * 0.58,
        9,
        8,
      );
    }
  }
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
  container.add([shadow, body, head, hair]);
  return { container, name, bubbleText: "", selected: false };
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
