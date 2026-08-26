import Phaser from "phaser";

export const TILE_SIZE = 32;

export const TILE = {
  grass: "tile-grass",
  grassDark: "tile-grass-dark",
  path: "tile-path",
  plaza: "tile-plaza",
  park: "tile-park",
  water: "tile-water",
  flowers: "tile-flowers",
  woodFloor: "tile-wood-floor",
  stoneFloor: "tile-stone-floor",
  wall: "tile-wall",
} as const;

function paintTexture(
  scene: Phaser.Scene,
  key: string,
  width: number,
  height: number,
  painter: (context: CanvasRenderingContext2D) => void,
): void {
  if (scene.textures.exists(key)) {
    return;
  }
  const texture = scene.textures.createCanvas(key, width, height);
  if (!texture) {
    throw new Error(`Unable to create pixel texture: ${key}`);
  }
  const context = texture.context;
  context.imageSmoothingEnabled = false;
  painter(context);
  texture.refresh();
}

function speckle(
  context: CanvasRenderingContext2D,
  color: string,
  points: ReadonlyArray<readonly [number, number]>,
): void {
  context.fillStyle = color;
  for (const [x, y] of points) {
    context.fillRect(x, y, 3, 3);
  }
}

export function createPixelTextures(scene: Phaser.Scene): void {
  paintTexture(scene, TILE.grass, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#79b85d";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    speckle(context, "#68aa51", [
      [3, 5],
      [23, 10],
      [13, 26],
    ]);
    speckle(context, "#92ca70", [
      [9, 16],
      [27, 29],
    ]);
  });

  paintTexture(scene, TILE.grassDark, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#69aa51";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    speckle(context, "#559544", [
      [4, 27],
      [18, 4],
      [27, 18],
    ]);
    speckle(context, "#83bd63", [
      [10, 12],
      [23, 29],
    ]);
  });

  paintTexture(scene, TILE.path, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#d9b978";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    speckle(context, "#c8a665", [
      [4, 8],
      [19, 23],
      [27, 5],
    ]);
    context.fillStyle = "#ead08e";
    context.fillRect(9, 15, 5, 3);
    context.fillRect(25, 29, 4, 3);
  });

  paintTexture(scene, TILE.plaza, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#dfc58e";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#cdb27e";
    context.fillRect(0, 15, 32, 2);
    context.fillRect(15, 0, 2, 32);
    context.fillStyle = "#ead6a5";
    context.fillRect(3, 3, 4, 3);
    context.fillRect(21, 21, 4, 3);
  });

  paintTexture(scene, TILE.park, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#75b965";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#8dcc73";
    context.fillRect(4, 6, 3, 8);
    context.fillRect(23, 19, 3, 7);
    context.fillStyle = "#5da34f";
    context.fillRect(7, 4, 3, 4);
    context.fillRect(20, 22, 3, 4);
  });

  paintTexture(scene, TILE.water, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#58a9c7";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#86d0df";
    context.fillRect(2, 7, 14, 3);
    context.fillRect(18, 22, 11, 3);
    context.fillStyle = "#3f92b6";
    context.fillRect(12, 15, 14, 3);
  });

  paintTexture(scene, TILE.flowers, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#79b85d";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    const flowers = [
      [8, 8, "#f3d46d"],
      [20, 11, "#f49bb1"],
      [13, 22, "#f0e7dc"],
      [26, 25, "#a891d4"],
    ] as const;
    for (const [x, y, color] of flowers) {
      context.fillStyle = "#4a9648";
      context.fillRect(x, y + 2, 2, 6);
      context.fillStyle = color;
      context.fillRect(x - 2, y, 6, 4);
      context.fillStyle = "#fff0a0";
      context.fillRect(x, y + 1, 2, 2);
    }
  });

  paintTexture(scene, TILE.woodFloor, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#c98e55";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#a86d40";
    context.fillRect(0, 15, 32, 2);
    context.fillRect(15, 0, 2, 15);
    context.fillRect(7, 17, 2, 15);
    context.fillStyle = "#dfaa68";
    context.fillRect(3, 5, 8, 2);
    context.fillRect(20, 23, 7, 2);
  });

  paintTexture(scene, TILE.stoneFloor, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#d9c99f";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#b8aa86";
    context.fillRect(0, 15, 32, 2);
    context.fillRect(15, 0, 2, 16);
    context.fillRect(7, 17, 2, 15);
    context.fillStyle = "#eee1bd";
    context.fillRect(3, 4, 5, 3);
  });

  paintTexture(scene, TILE.wall, TILE_SIZE, TILE_SIZE, (context) => {
    context.fillStyle = "#ead8a7";
    context.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    context.fillStyle = "#cfb879";
    context.fillRect(0, 24, TILE_SIZE, 8);
    context.fillStyle = "#f6e9c4";
    context.fillRect(4, 5, 24, 3);
    context.fillStyle = "#b69b62";
    context.fillRect(0, 30, TILE_SIZE, 2);
  });

  paintTexture(scene, "tree", 48, 64, (context) => {
    context.fillStyle = "rgba(38,65,43,.24)";
    context.fillRect(7, 52, 35, 7);
    context.fillStyle = "#68472f";
    context.fillRect(20, 34, 10, 21);
    context.fillStyle = "#875b36";
    context.fillRect(23, 35, 4, 20);
    context.fillStyle = "#2f7445";
    context.fillRect(6, 17, 36, 25);
    context.fillRect(12, 8, 27, 34);
    context.fillStyle = "#428c50";
    context.fillRect(5, 21, 13, 13);
    context.fillRect(29, 14, 13, 19);
    context.fillStyle = "#62a85c";
    context.fillRect(13, 7, 19, 12);
    context.fillRect(10, 19, 9, 8);
    context.fillStyle = "#7abd67";
    context.fillRect(17, 10, 9, 5);
  });

  paintTexture(scene, "bush", 28, 22, (context) => {
    context.fillStyle = "rgba(38,65,43,.22)";
    context.fillRect(3, 18, 22, 4);
    context.fillStyle = "#3f7a42";
    context.fillRect(2, 8, 24, 12);
    context.fillRect(6, 3, 16, 10);
    context.fillStyle = "#519455";
    context.fillRect(4, 6, 9, 8);
    context.fillRect(15, 2, 9, 7);
    context.fillStyle = "#6cae64";
    context.fillRect(9, 2, 7, 4);
    context.fillRect(3, 11, 6, 4);
  });

  paintTexture(scene, "lamp", 16, 40, (context) => {
    context.fillStyle = "rgba(255,226,120,.28)";
    context.fillRect(0, 0, 16, 16);
    context.fillStyle = "#36413d";
    context.fillRect(6, 12, 4, 25);
    context.fillRect(3, 8, 10, 7);
    context.fillStyle = "#ffe080";
    context.fillRect(5, 9, 6, 4);
  });
}
