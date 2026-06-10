// Keyless OSM raster basemap, used whenever a MapTiler style URL isn't
// configured — the map then renders without any API key (dev/demo). MapLibre
// accepts either a style URL string or a style object, so consumers don't care
// which one they get.
const osmFallbackStyle = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export const backend_url = process.env.NEXT_PUBLIC_DEVELOP_BACKEND_URL;
export const maptile_street = process.env.NEXT_PUBLIC_DEVELOP_MAPTILE_STREET || osmFallbackStyle;
export const maptile_satelite = process.env.NEXT_PUBLIC_DEVELOP_MAPTILE_SATELITE || osmFallbackStyle;
export const maptile_dark = process.env.NEXT_PUBLIC_DEVELOP_MAPTILE_DARK || osmFallbackStyle;
