import Phaser from "phaser";
import type { TiledObject } from "../map/tiled";

interface BuildingBounds {
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
}

export interface DollhouseBuildingView extends BuildingBounds {
  doorX: number;
  doorY: number;
}

export function drawDollhouseBuilding(
  scene: Phaser.Scene,
  location: TiledObject,
  kind: string,
  accentColor: number,
): DollhouseBuildingView {
  const bounds = buildingBounds(location);
  const graphics = scene.add.graphics().setDepth(bounds.depth);

  drawShell(graphics, bounds, kind, accentColor);
  if (kind === "cafe") {
    drawCafe(graphics, bounds, accentColor);
  } else if (kind === "library") {
    drawLibrary(graphics, bounds);
  } else if (kind === "market") {
    drawMarket(graphics, bounds);
  } else {
    drawCommonInterior(graphics, bounds, accentColor);
  }

  const doorX = bounds.x + bounds.width / 2;
  const doorY = bounds.y + bounds.height;
  drawDoor(graphics, doorX, doorY);

  return { ...bounds, doorX, doorY };
}

function buildingBounds(location: TiledObject): BuildingBounds {
  return {
    x: location.x + 10,
    y: location.y + 12,
    width: Math.max((location.width ?? 0) - 20, 1),
    height: Math.max((location.height ?? 0) - 22, 1),
    depth: location.y + (location.height ?? 0) - 8,
  };
}

function drawShell(
  graphics: Phaser.GameObjects.Graphics,
  bounds: BuildingBounds,
  kind: string,
  accentColor: number,
): void {
  const { x, y, width, height } = bounds;
  const floorColor = kind === "market" ? 0xc8b58b : 0xd8b77d;

  graphics.fillStyle(0x173126, 0.35);
  graphics.fillRect(x + 7, y + 7, width, height);
  graphics.fillStyle(0x5a3c2e, 1);
  graphics.fillRect(x - 6, y - 6, width + 12, height + 12);
  graphics.fillStyle(floorColor, 1);
  graphics.fillRect(x, y, width, height);

  graphics.lineStyle(1, 0x9d7652, 0.42);
  for (let plankY = y + 8; plankY < y + height; plankY += 9) {
    graphics.lineBetween(x, plankY, x + width, plankY);
  }

  graphics.fillStyle(0x6a4938, 1);
  graphics.fillRect(x, y, width, 8);
  graphics.fillRect(x, y, 7, height);
  graphics.fillRect(x + width - 7, y, 7, height);
  graphics.lineStyle(5, 0xf0dca7, 1);
  graphics.strokeRect(x - 3, y - 3, width + 6, height + 6);
  graphics.lineStyle(3, accentColor, 1);
  graphics.strokeRect(x - 6, y - 6, width + 12, height + 12);
}

function drawCafe(
  graphics: Phaser.GameObjects.Graphics,
  bounds: BuildingBounds,
  accentColor: number,
): void {
  const { x, y, width, height } = bounds;
  drawCounter(graphics, x + 14, y + 17, width * 0.52, 25);
  drawShelf(
    graphics,
    x + width - 36,
    y + 15,
    23,
    height * 0.42,
    [0xd75b48, 0x68a989, 0xe1bc54],
  );
  drawTableSet(graphics, x + width * 0.28, y + height * 0.67);
  drawTableSet(graphics, x + width * 0.68, y + height * 0.62);
  graphics.fillStyle(accentColor, 1);
  graphics.fillRect(x + width * 0.44, y + height * 0.45, width * 0.2, 7);
}

function drawLibrary(
  graphics: Phaser.GameObjects.Graphics,
  bounds: BuildingBounds,
): void {
  const { x, y, width, height } = bounds;
  const bookColors = [0xa44943, 0x557bb2, 0xd6a44e, 0x6b9e68];
  drawShelf(graphics, x + 13, y + 15, 24, height * 0.68, bookColors);
  drawShelf(graphics, x + width - 37, y + 15, 24, height * 0.68, bookColors);
  drawLongTable(graphics, x + width / 2, y + height * 0.48, width * 0.42);
  drawLongTable(graphics, x + width / 2, y + height * 0.72, width * 0.34);
}

function drawMarket(
  graphics: Phaser.GameObjects.Graphics,
  bounds: BuildingBounds,
): void {
  const { x, y, width, height } = bounds;
  drawCounter(graphics, x + 15, y + 16, width - 30, 23);
  drawProduceStall(
    graphics,
    x + 18,
    y + height * 0.42,
    width * 0.27,
    [0xe55d45, 0xe3b94c],
  );
  drawProduceStall(
    graphics,
    x + width * 0.365,
    y + height * 0.42,
    width * 0.27,
    [0x68a354, 0xe9d777],
  );
  drawProduceStall(
    graphics,
    x + width * 0.68,
    y + height * 0.42,
    width * 0.25,
    [0xd98054, 0x8bb65e],
  );
}

function drawCommonInterior(
  graphics: Phaser.GameObjects.Graphics,
  bounds: BuildingBounds,
  accentColor: number,
): void {
  const { x, y, width, height } = bounds;
  graphics.fillStyle(accentColor, 0.7);
  graphics.fillRect(
    x + width * 0.22,
    y + height * 0.26,
    width * 0.56,
    height * 0.46,
  );
  drawLongTable(graphics, x + width / 2, y + height / 2, width * 0.36);
  drawShelf(
    graphics,
    x + 14,
    y + 16,
    24,
    height * 0.55,
    [0xd7b95d, 0x6f96b5, 0xcc7569],
  );
}

function drawCounter(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  graphics.fillStyle(0x4e3227, 1);
  graphics.fillRect(x, y, width, height);
  graphics.fillStyle(0x8d5b3c, 1);
  graphics.fillRect(x + 4, y + 5, width - 8, height - 9);
  graphics.fillStyle(0xd4a064, 1);
  graphics.fillRect(x - 3, y - 4, width + 6, 7);
}

function drawShelf(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  height: number,
  colors: readonly number[],
): void {
  graphics.fillStyle(0x4d3328, 1);
  graphics.fillRect(x, y, width, height);
  for (let shelfY = y + 7; shelfY < y + height - 6; shelfY += 12) {
    for (let itemX = x + 4; itemX < x + width - 3; itemX += 7) {
      const colorIndex = Math.floor(itemX + shelfY) % colors.length;
      graphics.fillStyle(colors[colorIndex] ?? 0xd6a44e, 1);
      graphics.fillRect(itemX, shelfY, 5, 8);
    }
    graphics.fillStyle(0x805438, 1);
    graphics.fillRect(x + 2, shelfY + 8, width - 4, 3);
  }
}

function drawTableSet(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
): void {
  graphics.fillStyle(0x51362b, 1);
  graphics.fillRect(x - 18, y - 13, 36, 26);
  graphics.fillStyle(0xb77d4d, 1);
  graphics.fillRect(x - 14, y - 9, 28, 18);
  graphics.fillStyle(0x744b37, 1);
  graphics.fillRect(x - 28, y - 9, 7, 18);
  graphics.fillRect(x + 21, y - 9, 7, 18);
  graphics.fillStyle(0xeed8a3, 1);
  graphics.fillRect(x - 4, y - 4, 8, 6);
}

function drawLongTable(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
): void {
  graphics.fillStyle(0x57392d, 1);
  graphics.fillRect(x - width / 2, y - 9, width, 19);
  graphics.fillStyle(0xa66f48, 1);
  graphics.fillRect(x - width / 2 + 4, y - 6, width - 8, 12);
  graphics.fillStyle(0x6d4935, 1);
  graphics.fillRect(x - width * 0.3, y - 17, 11, 6);
  graphics.fillRect(x + width * 0.3 - 11, y + 12, 11, 6);
}

function drawProduceStall(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
  width: number,
  colors: readonly [number, number],
): void {
  const height = 42;
  graphics.fillStyle(0x50382d, 1);
  graphics.fillRect(x, y, width, height);
  graphics.fillStyle(0xb77a46, 1);
  graphics.fillRect(x + 4, y + 4, width - 8, height - 8);
  for (let row = 0; row < 2; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      graphics.fillStyle(
        colors[(row + column) % colors.length] ?? colors[0],
        1,
      );
      graphics.fillRect(
        x + 8 + column * ((width - 15) / 4),
        y + 8 + row * 15,
        7,
        7,
      );
    }
  }
}

function drawDoor(
  graphics: Phaser.GameObjects.Graphics,
  x: number,
  y: number,
): void {
  graphics.fillStyle(0x382820, 1);
  graphics.fillRect(x - 13, y - 23, 26, 23);
  graphics.fillStyle(0xd5ae68, 1);
  graphics.fillRect(x - 7, y - 4, 14, 4);
}
