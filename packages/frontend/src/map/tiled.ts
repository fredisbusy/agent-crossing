import rawTownMap from "../../../shared/assets/briar-cove.tmj?raw";

export interface TiledProperty {
  name: string;
  type: string;
  value: string | number | boolean;
}

export interface TiledPoint {
  x: number;
  y: number;
}

export interface TiledObject extends TiledPoint {
  id: number;
  name: string;
  type: string;
  width?: number;
  height?: number;
  point?: boolean;
  polyline?: TiledPoint[];
  properties?: TiledProperty[];
}

export interface TiledLayer {
  id: number;
  name: string;
  type: string;
  objects?: TiledObject[];
  visible: boolean;
}

export interface TiledMapData {
  width: number;
  height: number;
  tilewidth: number;
  tileheight: number;
  layers: TiledLayer[];
  properties?: TiledProperty[];
}

export const townMap: TiledMapData = JSON.parse(rawTownMap) as TiledMapData;

export function getLayer(name: string): TiledObject[] {
  return townMap.layers.find((layer) => layer.name === name)?.objects ?? [];
}

export function getProperty(
  object: TiledObject,
  name: string,
  fallback = "",
): string {
  const value = object.properties?.find(
    (property) => property.name === name,
  )?.value;
  return value === undefined ? fallback : String(value);
}

export function getMapProperty(name: string, fallback = ""): string {
  const value = townMap.properties?.find(
    (property) => property.name === name,
  )?.value;
  return value === undefined ? fallback : String(value);
}

export function parseColor(value: string, fallback: number): number {
  const normalized = value.replace("#", "").slice(-6);
  const parsed = Number.parseInt(normalized, 16);
  return Number.isNaN(parsed) ? fallback : parsed;
}
