import Phaser from "phaser";
import { TILE_SIZE } from "../../town-layout";
import { buildFallbackMap } from "./fallback-map";
import { extractLocationAreas, type LocationArea } from "./locations";
import { GROUND_LAYER, LOCATIONS_LAYER, TILESET_NAME } from "./tiled-types";
import { paintTileset, TILESET_PIXEL_HEIGHT, TILESET_PIXEL_WIDTH } from "./tileset-art";

export const TOWN_MAP_KEY = "town";
export const FALLBACK_MAP_KEY = "town-fallback";
export const TILESET_TEXTURE_KEY = "town-tiles-art";
/** vite `publicDir`(`packages/shared/maps`) 기준 경로. */
export const TOWN_MAP_URL = "town.json";

export interface TownMap {
  widthPx: number;
  heightPx: number;
  areas: LocationArea[];
  usedFallback: boolean;
}

export function preloadTownMap(scene: Phaser.Scene): void {
  // 파일이 없어도 장면은 계속 진행하고, 이후 대체 맵을 쓴다.
  scene.load.tilemapTiledJSON(TOWN_MAP_KEY, TOWN_MAP_URL);
}

function ensureTilesetTexture(scene: Phaser.Scene): void {
  if (scene.textures.exists(TILESET_TEXTURE_KEY)) return;
  const texture = scene.textures.createCanvas(TILESET_TEXTURE_KEY, TILESET_PIXEL_WIDTH, TILESET_PIXEL_HEIGHT);
  if (!texture) return;
  paintTileset(texture.getContext());
  texture.refresh();
}

function tryBuild(scene: Phaser.Scene, key: string, usedFallback: boolean): TownMap | null {
  if (!scene.cache.tilemap.exists(key)) return null;
  const tilemap = scene.make.tilemap({ key });
  const tileset = tilemap.addTilesetImage(TILESET_NAME, TILESET_TEXTURE_KEY, TILE_SIZE, TILE_SIZE, 0, 0, 1);
  if (!tileset) return null;
  const layer = tilemap.createLayer(GROUND_LAYER, tileset, 0, 0);
  if (!layer) return null;
  // `collision` 레이어는 백엔드 경로 탐색 전용이라 그리지 않는다.
  const objects = tilemap.getObjectLayer(LOCATIONS_LAYER)?.objects ?? [];
  return {
    widthPx: tilemap.widthInPixels,
    heightPx: tilemap.heightInPixels,
    areas: extractLocationAreas(objects),
    usedFallback,
  };
}

/** `town.json`을 그리고, 없거나 잘못됐으면 내장 대체 맵을 그린다. */
export function buildTownMap(scene: Phaser.Scene): TownMap {
  ensureTilesetTexture(scene);
  const loaded = tryBuild(scene, TOWN_MAP_KEY, false);
  if (loaded) return loaded;
  if (!scene.cache.tilemap.exists(FALLBACK_MAP_KEY)) {
    scene.cache.tilemap.add(FALLBACK_MAP_KEY, {
      format: Phaser.Tilemaps.Formats.TILED_JSON,
      data: buildFallbackMap(),
    });
  }
  const fallback = tryBuild(scene, FALLBACK_MAP_KEY, true);
  if (!fallback) throw new Error("내장 대체 맵을 그리지 못했다.");
  return fallback;
}
