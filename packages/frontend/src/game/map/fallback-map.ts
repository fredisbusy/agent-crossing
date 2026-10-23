import {
  CAFE,
  CAFE_DOOR,
  CROSS_ROAD,
  FALLBACK_AREAS,
  FALLBACK_MAP_HEIGHT,
  FALLBACK_MAP_WIDTH,
  MAIN_ROAD,
  POND,
  PLAZA,
  SHOP,
  SHOP_DOOR,
} from "../../town-layout";
import {
  COLLISION_LAYER,
  GROUND_LAYER,
  LOCATION_PATH_PROPERTY,
  LOCATIONS_LAYER,
  rectContains,
  TILE,
  TILE_SIZE,
  TILESET_NAME,
  type TileRect,
  type TiledMap,
} from "../../tiled";

export const TILE_COUNT = 8;
const BLOCKING = new Set<number>([TILE.wall, TILE.water, TILE.furniture, TILE.tree]);

function onBorder(rect: TileRect, x: number, y: number): boolean {
  return (
    rectContains(rect, x, y) &&
    (x === rect.x || y === rect.y || x === rect.x + rect.width - 1 || y === rect.y + rect.height - 1)
  );
}

function isTree(x: number, y: number): boolean {
  const edge = x < 2 || y < 2 || x >= FALLBACK_MAP_WIDTH - 2 || y >= FALLBACK_MAP_HEIGHT - 2;
  // 의사 무작위지만 결정론적인 흩뿌림.
  return edge || (x * 7 + y * 13) % 29 === 0;
}

function groundAt(x: number, y: number): number {
  if (x === CAFE_DOOR.x && y === CAFE_DOOR.y) return TILE.door;
  if (x === SHOP_DOOR.x && y === SHOP_DOOR.y) return TILE.door;
  if (onBorder(CAFE, x, y) || onBorder(SHOP, x, y)) return TILE.wall;
  if (rectContains(CAFE, x, y)) return y === CAFE.y + 1 && x > CAFE.x + 1 && x < CAFE.x + CAFE.width - 2 ? TILE.furniture : TILE.floor;
  if (rectContains(SHOP, x, y)) return y === SHOP.y + SHOP.height - 2 && x > SHOP.x && x < SHOP.x + 5 ? TILE.furniture : TILE.floor;
  if (rectContains(POND, x, y)) return TILE.water;
  const paths =
    rectContains(MAIN_ROAD, x, y) ||
    rectContains(CROSS_ROAD, x, y) ||
    rectContains(PLAZA, x, y) ||
    (x === CAFE_DOOR.x && y > CAFE_DOOR.y && y < MAIN_ROAD.y) ||
    (x === SHOP_DOOR.x && y < SHOP_DOOR.y && y >= MAIN_ROAD.y);
  if (paths) return TILE.road;
  return isTree(x, y) ? TILE.tree : TILE.grass;
}

/** town.json이 없을 때 쓰는 작은 내장 마을. */
export function buildFallbackMap(): TiledMap {
  const ground: number[] = [];
  for (let y = 0; y < FALLBACK_MAP_HEIGHT; y += 1) {
    for (let x = 0; x < FALLBACK_MAP_WIDTH; x += 1) ground.push(groundAt(x, y));
  }
  const collision = ground.map((gid) => (BLOCKING.has(gid) ? 1 : 0));
  const layerBase = { x: 0, y: 0, opacity: 1, visible: true };
  return {
    type: "map",
    version: "1.10",
    tiledversion: "1.10.2",
    orientation: "orthogonal",
    renderorder: "right-down",
    infinite: false,
    width: FALLBACK_MAP_WIDTH,
    height: FALLBACK_MAP_HEIGHT,
    tilewidth: TILE_SIZE,
    tileheight: TILE_SIZE,
    nextlayerid: 4,
    nextobjectid: FALLBACK_AREAS.length + 1,
    tilesets: [
      {
        firstgid: 1,
        name: TILESET_NAME,
        tilewidth: TILE_SIZE,
        tileheight: TILE_SIZE,
        tilecount: TILE_COUNT,
        columns: TILE_COUNT,
        image: "town-tiles.png",
        imagewidth: TILE_SIZE * TILE_COUNT,
        imageheight: TILE_SIZE,
        margin: 0,
        spacing: 0,
      },
    ],
    layers: [
      { ...layerBase, type: "tilelayer", id: 1, name: GROUND_LAYER, width: FALLBACK_MAP_WIDTH, height: FALLBACK_MAP_HEIGHT, data: ground },
      { ...layerBase, type: "tilelayer", id: 2, name: COLLISION_LAYER, width: FALLBACK_MAP_WIDTH, height: FALLBACK_MAP_HEIGHT, data: collision, visible: false },
      {
        ...layerBase,
        type: "objectgroup",
        id: 3,
        name: LOCATIONS_LAYER,
        draworder: "topdown",
        objects: FALLBACK_AREAS.map((area, index) => ({
          id: index + 1,
          name: area.location_path.split(" > ").pop() ?? area.location_path,
          type: "",
          x: area.rect.x * TILE_SIZE,
          y: area.rect.y * TILE_SIZE,
          width: area.rect.width * TILE_SIZE,
          height: area.rect.height * TILE_SIZE,
          rotation: 0,
          visible: true,
          properties: [{ name: LOCATION_PATH_PROPERTY, type: "string", value: area.location_path }],
        })),
      },
    ],
  };
}
