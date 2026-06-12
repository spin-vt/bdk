/**
 * The studio map island (back-end/static/app/map.js) — browser-side behavior
 * pinned in jsdom with a fake maplibre. What matters here:
 *
 *  - the point popup is single-source-of-truth: the header (address, BSL
 *    number, served) renders instantly from tile properties, and the plan
 *    lines come ONLY from /map/location/<id>?folder= — never a file-level
 *    guess that could flash to a different value;
 *  - modifying a saved edit reshapes THAT polygon: the edit's persisted shape
 *    leaves the edit-boxes layer while it's open in the inspector (no
 *    second polygon), and saving swaps the new shape in, in place;
 *  - the editing polygon exposes midpoint handles that insert a new vertex.
 */

const SQUARE_RING = [
  [-80, 37],
  [-79.9, 37],
  [-79.9, 37.1],
  [-80, 37.1],
  [-80, 37],
];
const SQUARE_FEATURE = {
  type: "Feature",
  properties: {},
  geometry: { type: "Polygon", coordinates: [SQUARE_RING] },
};

const CONFIG = {
  folderId: 5,
  tileUrl: "/api/tiles/5/{z}/{x}/{y}.pbf",
  basemapStyle: null,
  layers: [{ name: "sector.geojson", type: "wireless", tech: 70 }],
  bounds: null,
  exclusionBoxes: [
    {
      type: "Feature",
      properties: { editfileId: 7, name: "edit-7" },
      geometry: { type: "Polygon", coordinates: [SQUARE_RING] },
    },
  ],
  techs: [70],
  techNames: { 70: "Unlicensed FW" },
  techColors: { 70: "#0E7C86" },
  plansByTech: { 70: [{ id: 1, name: "AirLink 100" }, { id: 2, name: "AirLink Lite" }] },
  readOnly: false,
  hasFabric: false,
};

// ------------------------------------------------------------- fake maplibre

function FakeMap() {
  this.handlers = {}; // "event:layer" (layer empty for bare) -> [fn]
  this.sources = {};
  this.layers = {};
  this.canvas = { style: {} };
  this.dragPan = { enable() {}, disable() {} };
  this.doubleClickZoom = { enable() {}, disable() {} };
  this.queryHook = () => [];
}
FakeMap.prototype.on = function (event, a, b) {
  const key = typeof a === "function" ? `${event}:` : `${event}:${a}`;
  const fn = typeof a === "function" ? a : b;
  (this.handlers[key] = this.handlers[key] || []).push(fn);
};
FakeMap.prototype.once = FakeMap.prototype.on;
FakeMap.prototype.fire = function (event, layer, e) {
  const key = `${event}:${layer || ""}`;
  (this.handlers[key] || []).splice(0).forEach((fn) => fn(e));
};
FakeMap.prototype.firePersistent = function (event, layer, e) {
  (this.handlers[`${event}:${layer || ""}`] || []).forEach((fn) => fn(e));
};
FakeMap.prototype.addControl = function () {};
FakeMap.prototype.addSource = function (id, def) {
  const src = {
    def,
    data: def.data,
    setDataCalls: [],
    setData(d) {
      this.data = d;
      this.setDataCalls.push(d);
    },
    setTiles() {},
  };
  this.sources[id] = src;
};
FakeMap.prototype.getSource = function (id) {
  return this.sources[id];
};
FakeMap.prototype.addLayer = function (def) {
  this.layers[def.id] = def;
};
FakeMap.prototype.getLayer = function (id) {
  return this.layers[id];
};
FakeMap.prototype.setLayoutProperty = function () {};
FakeMap.prototype.setFeatureState = function () {};
FakeMap.prototype.removeFeatureState = function () {};
FakeMap.prototype.queryRenderedFeatures = function (q, opts) {
  return this.queryHook(q, opts) || [];
};
FakeMap.prototype.project = function (c) {
  return { x: c[0] * 1000, y: -c[1] * 1000 };
};
FakeMap.prototype.getZoom = function () {
  return 14;
};
FakeMap.prototype.fitBounds = function () {};
FakeMap.prototype.flyTo = function () {};
FakeMap.prototype.getCanvas = function () {
  return this.canvas;
};

function loadIsland(config) {
  document.body.innerHTML =
    `<script id="bdk-map-config" type="application/json">${JSON.stringify(config)}</script>` +
    '<div id="map"></div><div id="map-status"></div><div id="edit-inspector" style="display:none"></div>';

  const fakeMap = new FakeMap();
  const popups = [];
  function FakePopup() {
    this.htmls = [];
    this.open = true;
    popups.push(this);
  }
  FakePopup.prototype.setLngLat = function () {
    return this;
  };
  FakePopup.prototype.setHTML = function (h) {
    this.htmls.push(h);
    return this;
  };
  FakePopup.prototype.addTo = function () {
    return this;
  };
  FakePopup.prototype.isOpen = function () {
    return this.open;
  };
  FakePopup.prototype.remove = function () {
    this.open = false;
  };

  const eventSources = [];
  function FakeEventSource(url) {
    this.url = url;
    this.listeners = {};
    eventSources.push(this);
  }
  FakeEventSource.prototype.addEventListener = function (ev, fn) {
    (this.listeners[ev] = this.listeners[ev] || []).push(fn);
  };
  FakeEventSource.prototype.close = function () {};

  global.maplibregl = {
    Map: function () {
      return fakeMap;
    },
    NavigationControl: function () {},
    ScaleControl: function () {},
    Popup: FakePopup,
  };
  global.EventSource = FakeEventSource;

  jest.isolateModules(() => {
    require("../../back-end/static/app/map.js");
  });
  fakeMap.fire("load", "");
  return { map: fakeMap, popups, eventSources };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

const jsonResponse = (data) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(data) });

afterEach(() => {
  delete global.fetch;
  delete window.BDKMap;
});

// -------------------------------------------------------------------- popup

describe("point popup", () => {
  it("renders the header (with the BSL number) instantly and plan lines only from the DB", async () => {
    global.fetch = jest.fn(() =>
      jsonResponse({
        status: "success",
        services: [
          { file: "fiber.kml", tech: 50, plan: "Fiber Gig", down: 1000, up: 1000 },
        ],
      })
    );
    const { map, popups } = loadIsland(CONFIG);

    map.firePersistent("click", "locations", {
      features: [
        {
          id: 999000111,
          properties: {
            address: "27892 OVER THE HILL DR",
            served: "True",
            bsl: "True",
            network_coverages: "sector.geojson",
            feature_type: "Point",
          },
        },
      ],
      lngLat: { lng: -79.95, lat: 37.05 },
    });

    expect(popups).toHaveLength(1);
    const first = popups[0].htmls[0];
    expect(first).toContain("27892 OVER THE HILL DR");
    expect(first).toContain("BSL # ");
    expect(first).toContain("999000111");
    // No file-level guess: no plan name or speeds until the DB answers.
    expect(first).not.toContain("Mbps");
    expect(first).not.toContain("AirLink");

    expect(global.fetch).toHaveBeenCalledWith(
      "/map/location/999000111?folder=5",
      expect.objectContaining({ credentials: "include" })
    );
    await flush();
    const second = popups[0].htmls[1];
    expect(second).toContain("Fiber Gig");
    expect(second).toContain("1000/1000 Mbps");
  });

  it("labels a non-BSL location as Location ID, not BSL #", () => {
    global.fetch = jest.fn(() => jsonResponse({ status: "success", services: [] }));
    const { map, popups } = loadIsland(CONFIG);
    map.firePersistent("click", "locations", {
      features: [
        { id: 42, properties: { address: "1 BARN RD", served: "False", bsl: "False" } },
      ],
      lngLat: { lng: -79.95, lat: 37.05 },
    });
    expect(popups[0].htmls[0]).toContain("Location ID ");
    expect(popups[0].htmls[0]).not.toContain("BSL # ");
    expect(global.fetch).not.toHaveBeenCalled(); // not served: nothing to ask
  });
});

// ----------------------------------------------------------- edit-an-edit

const LOCATION_IN_SQUARE = {
  id: 1001,
  properties: {
    location_id: 1001,
    served: "True",
    bsl: "True",
    network_coverages: "sector.geojson",
  },
  geometry: { type: "Point", coordinates: [-79.95, 37.05] },
};

async function openSavedEdit(handles) {
  global.fetch = jest.fn((url) => {
    if (url === "/map/edit/7")
      return jsonResponse({
        status: "success",
        id: 7,
        name: "edit-7",
        // Cloned: the island reshapes the ring in place, and a shared object
        // would leak one test's edits into the next.
        feature: JSON.parse(JSON.stringify(SQUARE_FEATURE)),
        markers: [{ id: 1001, editedFile: ["sector.geojson"] }],
      });
    if (url === "/map/edit/7/replace")
      return jsonResponse({ status: "success", task_id: "task-1" });
    return jsonResponse({ status: "success", features: [] });
  });
  const island = loadIsland(CONFIG);
  island.map.queryHook = (q, opts) => {
    if ((opts.layers || []).includes("locations")) return [LOCATION_IN_SQUARE];
    if ((opts.layers || []).includes("draw-temp-pts")) return handles.current;
    return [];
  };
  window.BDKMap.editSavedEdit(7);
  await flush();
  island.map.fire("idle", ""); // the post-zoom selection
  return island;
}

describe("modifying a saved edit", () => {
  it("shows ONE polygon while reshaping: the persisted shape leaves the layer", async () => {
    const handles = { current: [] };
    const { map } = await openSavedEdit(handles);

    const boxes = map.getSource("edit-boxes");
    const features = boxes.setDataCalls[boxes.setDataCalls.length - 1].features;
    // The pending (editable) copy is there; the saved shape is NOT also drawn.
    expect(features.some((f) => (f.properties || {}).editfileId === 7)).toBe(false);
    expect(features).toHaveLength(1);
  });

  it("offers midpoint handles and inserts a vertex when one is grabbed", async () => {
    const handles = { current: [] };
    const { map } = await openSavedEdit(handles);

    // The handle layer carries 4 vertex handles + 4 midpoints for a square.
    const temp = map.getSource("draw-temp");
    const handleFeats = temp.setDataCalls[temp.setDataCalls.length - 1].features;
    const mids = handleFeats.filter((f) => f.properties.mid);
    expect(handleFeats.filter((f) => f.properties.vertex != null)).toHaveLength(4);
    expect(mids).toHaveLength(4);

    // Grab the midpoint of the first edge: the ring gains a vertex there.
    handles.current = [{ properties: mids[0].properties }];
    map.firePersistent("mousedown", "", {
      point: { x: -79950, y: -37000 },
      lngLat: { lng: -79.95, lat: 37 },
    });
    const boxes = map.getSource("edit-boxes");
    const pendingFeat =
      boxes.setDataCalls[boxes.setDataCalls.length - 1].features[0];
    const ring = pendingFeat.geometry.coordinates[0];
    expect(ring).toHaveLength(6); // 5 (closed square) + the inserted vertex
    expect(ring[1]).toEqual([-79.95, 37]);

    // ...and it drags live.
    map.firePersistent("mousemove", "", { lngLat: { lng: -79.94, lat: 36.99 } });
    expect(ring[1]).toEqual([-79.94, 36.99]);
  });

  it("saving a reshaped polygon swaps the new shape into the saved-edit layer in place", async () => {
    const handles = { current: [] };
    const { map } = await openSavedEdit(handles);

    // Reshape: pull a new vertex out of the first edge's midpoint.
    const temp = map.getSource("draw-temp");
    const mids = temp.setDataCalls[temp.setDataCalls.length - 1].features.filter(
      (f) => f.properties.mid
    );
    handles.current = [{ properties: mids[0].properties }];
    map.firePersistent("mousedown", "", {
      point: { x: -79950, y: -37000 },
      lngLat: { lng: -79.95, lat: 37 },
    });
    map.firePersistent("mousemove", "", { lngLat: { lng: -79.94, lat: 36.95 } });
    map.firePersistent("mouseup", "", {});
    map.fire("idle", ""); // mouseup re-derives the selection
    await flush();

    document.querySelector("[data-inspector-save]").click();
    await flush();

    expect(global.fetch).toHaveBeenCalledWith(
      "/map/edit/7/replace",
      expect.objectContaining({ method: "POST" })
    );
    const boxes = map.getSource("edit-boxes");
    const features = boxes.setDataCalls[boxes.setDataCalls.length - 1].features;
    const mine = features.filter((f) => (f.properties || {}).editfileId === 7);
    expect(features).toHaveLength(1); // in place: never a second polygon
    expect(mine).toHaveLength(1);
    const ring = mine[0].geometry.coordinates[0];
    expect(ring).toHaveLength(6); // the inserted vertex survived the save
    expect(ring[1]).toEqual([-79.94, 36.95]);
  });
});
