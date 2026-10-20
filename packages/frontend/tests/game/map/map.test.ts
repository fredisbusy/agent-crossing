import { describe, expect, it } from "vitest";
import { buildFallbackMap, TILE, TILE_COUNT } from "../../../src/game/map/fallback-map";
import { extractLocationAreas } from "../../../src/game/map/locations";
import { LOCATIONS_LAYER, type TiledObjectLayer, type TiledTileLayer } from "../../../src/game/map/tiled-types";
import { CAFE_DOOR, locationPathAt } from "../../../src/town-layout";

describe("fallback map", () => {
  const map = buildFallbackMap();
  const ground = map.layers.find((layer): layer is TiledTileLayer => layer.type === "tilelayer" && layer.name === "ground");

  it("fills the ground layer with valid gids", () => {
    expect(ground?.data).toHaveLength(map.width * map.height);
    expect(ground?.data.every((gid) => gid >= 1 && gid <= TILE_COUNT)).toBe(true);
    expect(ground?.data[CAFE_DOOR.y * map.width + CAFE_DOOR.x]).toBe(TILE.door);
  });

  it("exposes locations that match the layout", () => {
    const layer = map.layers.find((l): l is TiledObjectLayer => l.type === "objectgroup" && l.name === LOCATIONS_LAYER);
    const areas = extractLocationAreas(layer?.objects ?? []);
    expect(areas.map((a) => a.location_path)).toContain("Town > Cafe");
    expect(locationPathAt(CAFE_DOOR.x, CAFE_DOOR.y - 1)).toBe("Town > Cafe");
    expect(locationPathAt(0, 0)).toBe("Town");
  });
});

describe("extractLocationAreas", () => {
  it("skips objects without a location_path", () => {
    const areas = extractLocationAreas([
      { name: "ok", x: 1, y: 2, width: 3, height: 4, properties: [{ name: "location_path", value: "Town > Ok" }] },
      { name: "no", x: 0, y: 0, width: 1, height: 1, properties: [] },
      null,
    ]);
    expect(areas).toEqual([{ name: "ok", location_path: "Town > Ok", x: 1, y: 2, width: 3, height: 4 }]);
  });
});
