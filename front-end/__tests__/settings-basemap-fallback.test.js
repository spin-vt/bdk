/**
 * The basemap settings must fall back to a keyless OSM raster style when the
 * MapTiler env vars are unset, so the map renders in dev without a key.
 * With a key configured, the style URL passes through unchanged.
 */

const loadSettings = (env) => {
  let mod;
  jest.isolateModules(() => {
    const prev = {};
    for (const [k, v] of Object.entries(env)) {
      prev[k] = process.env[k];
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
    mod = require("../utils/settings");
    for (const [k, v] of Object.entries(prev)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  });
  return mod;
};

describe("basemap fallback", () => {
  it("falls back to an OSM raster style object when no key is set", () => {
    const s = loadSettings({
      NEXT_PUBLIC_DEVELOP_MAPTILE_STREET: "",
      NEXT_PUBLIC_DEVELOP_MAPTILE_SATELITE: undefined,
      NEXT_PUBLIC_DEVELOP_MAPTILE_DARK: undefined,
    });
    for (const style of [s.maptile_street, s.maptile_satelite, s.maptile_dark]) {
      expect(typeof style).toBe("object");
      expect(style.version).toBe(8);
      expect(style.sources.osm.type).toBe("raster");
      expect(style.sources.osm.tiles[0]).toContain("openstreetmap.org");
    }
  });

  it("passes the configured style URL through unchanged", () => {
    const url = "https://api.maptiler.com/maps/streets/style.json?key=abc";
    const s = loadSettings({ NEXT_PUBLIC_DEVELOP_MAPTILE_STREET: url });
    expect(s.maptile_street).toBe(url);
  });
});
