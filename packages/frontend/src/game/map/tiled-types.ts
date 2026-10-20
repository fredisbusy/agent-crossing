/** Phaser가 읽는 Tiled 1.10 JSON 중 우리가 쓰는 부분. */

export const TILESET_NAME = "town-tiles";
export const GROUND_LAYER = "ground";
export const COLLISION_LAYER = "collision";
export const LOCATIONS_LAYER = "locations";
export const LOCATION_PATH_PROPERTY = "location_path";

export interface TiledProperty {
  name: string;
  type: string;
  value: string;
}

export interface TiledObject {
  id: number;
  name: string;
  type: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  visible: boolean;
  properties: TiledProperty[];
}

export interface TiledTileLayer {
  type: "tilelayer";
  id: number;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  opacity: number;
  visible: boolean;
  data: number[];
}

export interface TiledObjectLayer {
  type: "objectgroup";
  id: number;
  name: string;
  x: number;
  y: number;
  opacity: number;
  visible: boolean;
  draworder: "topdown";
  objects: TiledObject[];
}

export interface TiledTileset {
  firstgid: number;
  name: string;
  tilewidth: number;
  tileheight: number;
  tilecount: number;
  columns: number;
  image: string;
  imagewidth: number;
  imageheight: number;
  margin: number;
  spacing: number;
}

export interface TiledMap {
  type: "map";
  version: string;
  tiledversion: string;
  orientation: "orthogonal";
  renderorder: "right-down";
  infinite: false;
  width: number;
  height: number;
  tilewidth: number;
  tileheight: number;
  nextlayerid: number;
  nextobjectid: number;
  layers: (TiledTileLayer | TiledObjectLayer)[];
  tilesets: TiledTileset[];
}
