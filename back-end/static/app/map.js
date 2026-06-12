/* The studio map island. Standalone MapLibre, no framework.
 *
 * Boundary contract (proven by the SSR map prototype):
 *   server -> island: the #bdk-map-config JSON blob (filing, tiles, layers
 *     grouped by technology, plans for the inspector verbs, persisted edits);
 *   page -> island: window.BDKMap (visibility, edit mode, fly-to);
 *   island -> page: custom DOM events (bdk:edit-changed, bdk:edit-removed).
 *
 * Edits restyle instantly via setFeatureState (tiles carry stable feature ids
 * = location_id); the save dispatches the real edit chain and a short-lived
 * SSE stream reports the retile so the authoritative tiles swap in.
 */
(function () {
  "use strict";
  var cfgEl = document.getElementById("bdk-map-config");
  if (!cfgEl) return;
  var config = JSON.parse(cfgEl.textContent);
  if (!config) return;

  var SERVED = "#2E8540", BSL = "#C7472E", NONBSL = "#AEB2A8",
      EXCLUDED = "#B026FF", PARTIAL = "#E0A800", SELECTED = "#2D6CDF";

  var fallbackStyle = {
    version: 8,
    sources: { osm: { type: "raster",
      tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256, attribution: "© OpenStreetMap contributors" } },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };

  var map = new maplibregl.Map({
    container: "map",
    style: config.basemapStyle || fallbackStyle,
    center: [-98.35, 39.5],
    zoom: 4,
    transformRequest: function (url) {
      return url.indexOf("/api/tiles/") !== -1 ? { url: url, credentials: "include" } : undefined;
    },
  });
  map.addControl(new maplibregl.NavigationControl(), "bottom-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");

  var status = document.getElementById("map-status");
  function say(msg) { if (status) status.textContent = msg || ""; }

  var nameToTech = {};
  (config.layers || []).forEach(function (l) { nameToTech[l.name] = l.tech; });

  function techLayerIds(tech) {
    return (config.layers || [])
      .filter(function (l) { return l.tech === tech; })
      .map(function (l) { return (l.type === "wired" ? "wired-" : "wireless-") + l.name; });
  }

  function boxesFC() {
    // While a saved edit is open in the inspector, its persisted shape yields
    // to the editable (pending) copy — drawing both reads as a second polygon
    // the moment a vertex moves.
    var feats = persistedBoxes.filter(function (f) {
      return !(editingEdit && f.properties && f.properties.editfileId === editingEdit.id);
    }).concat(editBoxes.map(function (b) { return b.feature; }));
    if (pending) feats.push(pending.feature);
    return { type: "FeatureCollection", features: feats };
  }

  function addLayers() {
    var tilesAbs = window.location.origin + config.tileUrl;
    map.addSource("custom", { type: "vector", tiles: [tilesAbs], maxzoom: 16 });

    (config.layers || []).forEach(function (l) {
      var color = (config.techColors || {})[l.tech] || "#565EC1";
      // Layer ids derive from filenames (unique per filing since the upload
      // dedupe); skip rather than crash if a legacy duplicate slips through —
      // an addLayer throw here would kill every layer after it (locations!).
      if (map.getLayer((l.type === "wired" ? "wired-" : "wireless-") + l.name)) return;
      if (l.type === "wired") {
        map.addLayer({
          id: "wired-" + l.name, type: "line", source: "custom", "source-layer": "data",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": color, "line-width": 2 },
          filter: ["all", ["==", ["get", "feature_type"], "LineString"],
                          ["==", ["get", "network_coverages"], l.name]],
        });
      } else {
        map.addLayer({
          id: "wireless-" + l.name, type: "fill", source: "custom", "source-layer": "data",
          paint: { "fill-color": color, "fill-opacity": 0.35 },
          filter: ["all", ["any", ["==", ["get", "feature_type"], "Polygon"],
                                  ["==", ["get", "feature_type"], "MultiPolygon"]],
                          ["==", ["get", "network_coverages"], l.name]],
        });
      }
    });

    map.addSource("edit-boxes", { type: "geojson", data: boxesFC() });
    map.addLayer({ id: "edit-boxes-fill", type: "fill", source: "edit-boxes",
      paint: { "fill-color": EXCLUDED, "fill-opacity": 0.08 } });
    map.addLayer({ id: "edit-boxes-line", type: "line", source: "edit-boxes",
      paint: { "line-color": EXCLUDED, "line-width": 1.5, "line-dasharray": [2, 1] } });

    map.addSource("draw-temp", { type: "geojson",
      data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "draw-temp-line", type: "line", source: "draw-temp",
      paint: { "line-color": EXCLUDED, "line-width": 2, "line-dasharray": [2, 1] },
      filter: ["==", ["geometry-type"], "LineString"] });
    map.addLayer({ id: "draw-temp-pts", type: "circle", source: "draw-temp",
      paint: { "circle-radius": ["case", ["boolean", ["get", "first"], false], 6,
                                         ["boolean", ["get", "mid"], false], 3.5, 4],
               "circle-color": ["case", ["boolean", ["get", "mid"], false], EXCLUDED, "#fff"],
               "circle-stroke-color": ["case", ["boolean", ["get", "mid"], false], "#fff", EXCLUDED],
               "circle-stroke-width": 2 },
      filter: ["==", ["geometry-type"], "Point"] });

    // ONE points layer, colored by each location's own `served` flag (the
    // spike's correctness fix over the SPA's stacked layers).
    map.addLayer({
      id: "locations", type: "circle", source: "custom", "source-layer": "data",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 0.8, 12, 2.5, 15, 3.5],
        "circle-color": ["case",
          ["==", ["feature-state", "editstate"], "full"], EXCLUDED,
          ["==", ["feature-state", "editstate"], "partial"], PARTIAL,
          ["==", ["feature-state", "editstate"], "selected"], SELECTED,
          ["any", ["==", ["get", "served"], true],
                  ["==", ["get", "served"], "True"],
                  ["==", ["get", "served"], "true"]], SERVED,
          ["==", ["get", "bsl"], "True"], BSL,
          NONBSL],
      },
      filter: ["==", ["get", "feature_type"], "Point"],
    });

    // Plan lines come from ONE source of truth: /map/location/<id> (the kml
    // rows + governing plans in the DB). Tiles only know served/coverage —
    // never per-location plans — so rendering a file-level guess first made
    // the popup flash when an edit's plan differed. Now the header (address,
    // BSL number, served — all carried by the tile) shows instantly and the
    // plan lines fill in from the DB.
    function serviceLinesHtml(entries) {
      return entries.map(function (svc) {
        var plan = svc.plan
          ? '<span style="font-weight:600">' + svc.plan + "</span>"
          : '<span style="color:#999">no plan yet</span>';
        var speed = svc.down != null
          ? ' <span class="num">' + svc.down + "/" + svc.up + " Mbps</span>" : "";
        var techName = (config.techNames || {})[svc.tech] || "coverage";
        return '<div style="margin-top:6px">' + plan + speed +
          '<div style="font-size:11px;color:#999">' + techName + " · " + svc.file + "</div></div>";
      }).join("");
    }

    map.on("click", "locations", function (e) {
      if (editMode || suppressClick) return;
      var f = e.features[0], p = f.properties || {};
      var served = p.served === true || p.served === "True" || p.served === "true";
      var locId = f.id != null ? f.id : p.location_id;
      var header = '<div style="font-size:12.5px"><b>' + (p.address || ("Location " + locId)) + "</b>" +
        (locId != null
          ? '<div style="font-size:11px;color:#999">' + (p.bsl === "True" ? "BSL # " : "Location ID ") +
            '<span class="num">' + locId + "</span></div>"
          : "") +
        (served ? '<span style="color:' + SERVED + '">served</span>'
                : p.bsl === "True" ? '<span style="color:' + BSL + '">not served</span>'
                                   : "non-BSL");
      var loading = served && locId != null;
      var popup = new maplibregl.Popup({ closeButton: false })
        .setLngLat(e.lngLat)
        .setHTML(header + (loading ? '<div style="margin-top:6px;color:#999">…</div>' : "") + "</div>")
        .addTo(map);
      if (loading) {
        fetch("/map/location/" + locId + "?folder=" + config.folderId, { credentials: "include" })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (!popup.isOpen()) return;
            var lines = d.status === "success" && (d.services || []).length
              ? serviceLinesHtml(d.services)
              : '<div style="margin-top:6px;color:#999">plan details unavailable</div>';
            popup.setHTML(header + lines + "</div>");
          })
          .catch(function () {
            if (popup.isOpen())
              popup.setHTML(header + '<div style="margin-top:6px;color:#999">plan details unavailable</div>' + "</div>");
          });
      }
    });
    map.on("mouseenter", "locations", function () { if (!editMode) map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "locations", function () { if (!editMode) map.getCanvas().style.cursor = ""; });
  }

  map.on("load", function () {
    addLayers();
    if (config.bounds) map.fitBounds(config.bounds, { padding: 60, duration: 0 });
    // Deep links from the files page: ?show_edit=<id> zooms to a saved edit,
    // ?edit_edit=<id> opens it for modifying.
    var params = new URLSearchParams(window.location.search);
    var showId = Number(params.get("show_edit"));
    var editId = Number(params.get("edit_edit"));
    if (showId || editId) map.once("idle", function () {
      if (showId) zoomToEdit(showId);
      else if (editId) startEditOfEdit(editId);
    });
  });

  // ---------------------------------------------------------------- edit state
  var isServed = function (p) {
    return p && (p.served === true || p.served === "True" || p.served === "true");
  };
  var coveredByOf = function (props) {
    return String(props.network_coverages || "").split(/,\s*/)
      .map(function (s) { return s.trim(); }).filter(Boolean);
  };

  var editMode = false, editTool = "polygon";
  var editBoxes = [];       // committed this session: {feature, markers:[{id, editedFile, plan_id?, st}]}
  var pending = null;       // open inspector: {feature, points, perTech, actions}
  var editingEdit = null;   // a SAVED edit being modified: {id, name, markers, presetActions, ring}
  var persistedBoxes = (config.exclusionBoxes || []).slice();
  var polyVerts = [];
  var sessionSeq = 0;
  var dragVertex = null;    // index of the editing polygon's vertex being dragged
  var suppressClick = false; // swallow the click that ends a vertex drag

  function ringOfFeature(f) {
    return (f && f.geometry && f.geometry.type === "Polygon" && f.geometry.coordinates[0]) || null;
  }
  function bboxOfRing(ring) {
    var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    ring.forEach(function (c) {
      minx = Math.min(minx, c[0]); maxx = Math.max(maxx, c[0]);
      miny = Math.min(miny, c[1]); maxy = Math.max(maxy, c[1]);
    });
    return [[minx, miny], [maxx, maxy]];
  }
  function zoomToEdit(editfileId, then) {
    var f = persistedBoxes.filter(function (b) {
      return b.properties && b.properties.editfileId === editfileId;
    })[0];
    var ring = ringOfFeature(f);
    if (!ring || !ring.length) return false;
    map.fitBounds(bboxOfRing(ring), { padding: 90, maxZoom: 17, duration: 500 });
    if (then) map.once("idle", then);
    return true;
  }
  // The saved picks → per-tech verbs, to prefill the inspector.
  function actionsFromMarkers(markers) {
    var actions = {};
    (markers || []).forEach(function (m) {
      (m.editedFile || []).forEach(function (name) {
        var t = nameToTech[name];
        if (t != null) actions[t] = m.plan_id ? "plan:" + m.plan_id : "exclude";
      });
    });
    return actions;
  }

  function setState(id, st) {
    if (st) map.setFeatureState({ source: "custom", sourceLayer: "data", id: id }, { editstate: st });
    else map.removeFeatureState({ source: "custom", sourceLayer: "data", id: id }, "editstate");
  }
  function refreshBoxes() {
    var s = map.getSource("edit-boxes");
    if (s) s.setData(boxesFC());
  }
  function emitChanged() {
    refreshBoxes();
    document.dispatchEvent(new CustomEvent("bdk:edit-changed", {
      detail: { count: editBoxes.reduce(function (n, b) { return n + b.markers.length; }, 0),
                boxes: editBoxes.length },
    }));
  }

  function applyEditMode(on) {
    editMode = on;
    if (on) {
      window.BDKMap.setLocationsVisible(true);
      applyTool(editTool);
    } else {
      map.dragPan.enable();
      map.doubleClickZoom.enable();
      map.getCanvas().style.cursor = "";
      cancelPolyDraw();
      if (pending) cancelInspector();
      editingEdit = null;
    }
  }
  function applyTool(tool) {
    editTool = tool;
    if (!editMode) return;
    cancelPolyDraw();
    if (pending) cancelInspector();
    if (tool === "polygon") {
      map.dragPan.enable(); map.doubleClickZoom.disable();
      map.getCanvas().style.cursor = "crosshair";
    } else {
      map.dragPan.enable(); map.doubleClickZoom.enable();
      map.getCanvas().style.cursor = "pointer";
    }
  }

  function pointInRing(lng, lat, ring) {
    var inside = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function collectPointsInRing(ring, editing) {
    // Served points inside the ring — plus, while modifying a saved edit, the
    // points its picks already act on (they render unserved precisely BECAUSE
    // of this edit, so the served filter alone would lose them).
    var markerById = {};
    if (editing) (editing.markers || []).forEach(function (m) { markerById[m.id] = m; });
    var px = ring.map(function (c) { return map.project(c); });
    var xs = px.map(function (p) { return p.x; }), ys = px.map(function (p) { return p.y; });
    var feats = map.queryRenderedFeatures(
      [[Math.min.apply(null, xs), Math.min.apply(null, ys)],
       [Math.max.apply(null, xs), Math.max.apply(null, ys)]],
      { layers: ["locations"] });
    var points = [], seen = {};
    feats.forEach(function (f) {
      var id = f.id != null ? f.id : f.properties.location_id;
      if (id == null || seen[id]) return;
      var marked = markerById[id];
      if (!isServed(f.properties) && !marked) return;
      var c = f.geometry && f.geometry.coordinates;
      if (!c || !pointInRing(c[0], c[1], ring)) return;
      seen[id] = true;
      var coveredBy = coveredByOf(f.properties);
      if (marked) (marked.editedFile || []).forEach(function (n) {
        if (coveredBy.indexOf(n) === -1) coveredBy.push(n);
      });
      if (coveredBy.length) points.push({ id: id, coveredBy: coveredBy });
    });
    return points;
  }

  function selectInRing(ring) {
    var points = collectPointsInRing(ring, editingEdit);
    if (!points.length && !editingEdit) { say("No served locations in that area."); return; }
    if (editingEdit) editingEdit.ring = ring;
    var feature = { type: "Feature", properties: { sessionId: ++sessionSeq },
      geometry: { type: "Polygon", coordinates: [ring] } };
    openInspector(feature, points);
  }

  // freeform polygon tool
  function tempFC() {
    var feats = [];
    if (polyVerts.length > 1) {
      var line = polyVerts.concat(polyVerts.length > 2 ? [polyVerts[0]] : []);
      feats.push({ type: "Feature", properties: {},
        geometry: { type: "LineString", coordinates: line } });
    }
    polyVerts.forEach(function (c, i) {
      feats.push({ type: "Feature", properties: { first: i === 0 },
        geometry: { type: "Point", coordinates: c } });
    });
    return { type: "FeatureCollection", features: feats };
  }
  function refreshTemp() {
    var s = map.getSource("draw-temp");
    if (s) s.setData(tempFC());
  }
  function cancelPolyDraw() { polyVerts = []; refreshTemp(); }
  function closePolygon() {
    if (polyVerts.length < 3) { cancelPolyDraw(); return; }
    var ring = polyVerts.concat([polyVerts[0]]);
    cancelPolyDraw();
    selectInRing(ring);
  }
  map.on("click", function (e) {
    if (suppressClick) return;
    if (!editMode) {
      // Browse mode: clicking a saved edit's shape (not a location dot) opens
      // it for modifying — picks, vertices, or delete.
      if (config.readOnly || !map.getLayer("edit-boxes-fill")) return;
      if (map.queryRenderedFeatures(e.point, { layers: ["locations"] }).length) return;
      var browseHits = map.queryRenderedFeatures(e.point, { layers: ["edit-boxes-fill"] });
      if (!browseHits.length) return;
      var bp = browseHits[0].properties || {};
      if (bp.editfileId != null)
        document.dispatchEvent(new CustomEvent("bdk:edit-open",
          { detail: { editfileId: Number(bp.editfileId) } }));
      return;
    }
    if (pending) return;
    if (editTool === "polygon") {
      if (polyVerts.length >= 3) {
        var p0 = map.project(polyVerts[0]);
        if (Math.hypot(p0.x - e.point.x, p0.y - e.point.y) < 10) { closePolygon(); return; }
      }
      polyVerts.push([e.lngLat.lng, e.lngLat.lat]);
      refreshTemp();
    }
  });

  // ---------------------------------------- vertex dragging (edit-an-edit)
  // While a saved edit is open, its polygon's vertices render as handles that
  // drag directly — reshaping never needs a separate mode or redraw. Each
  // edge's midpoint renders as a smaller handle; grabbing one inserts a new
  // vertex there and the drag continues on it.
  function showVertexHandles() {
    var ring = editingEdit && editingEdit.ring;
    var s = map.getSource("draw-temp");
    if (!s) return;
    if (!ring) { s.setData({ type: "FeatureCollection", features: [] }); return; }
    var verts = ring.slice(0, -1);
    var feats = verts.map(function (c, i) {
      return { type: "Feature", properties: { first: false, vertex: i },
        geometry: { type: "Point", coordinates: c } };
    });
    verts.forEach(function (c, i) {
      var d = verts[(i + 1) % verts.length];
      feats.push({ type: "Feature", properties: { first: false, mid: true, midpoint: i },
        geometry: { type: "Point", coordinates: [(c[0] + d[0]) / 2, (c[1] + d[1]) / 2] } });
    });
    s.setData({ type: "FeatureCollection", features: feats });
  }
  map.on("mousedown", function (e) {
    if (!editingEdit || !pending) return;
    var hits = map.queryRenderedFeatures(
      [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]],
      { layers: ["draw-temp-pts"] });
    // A vertex outranks a midpoint when both are under the cursor.
    var vert = null, mid = null;
    hits.forEach(function (h) {
      var hp = h.properties || {};
      if (vert == null && hp.vertex != null) vert = Number(hp.vertex);
      if (mid == null && hp.mid && hp.midpoint != null) mid = Number(hp.midpoint);
    });
    if (vert != null) {
      dragVertex = vert;
    } else if (mid != null) {
      var ring = editingEdit.ring;
      ring.splice(mid + 1, 0, [e.lngLat.lng, e.lngLat.lat]);
      dragVertex = mid + 1;
      if (pending) pending.feature.geometry.coordinates = [ring];
      showVertexHandles();
      refreshBoxes();
    } else return;
    map.dragPan.disable();
    map.getCanvas().style.cursor = "grabbing";
  });
  map.on("mousemove", function (e) {
    if (dragVertex == null || !editingEdit) return;
    var ring = editingEdit.ring;
    ring[dragVertex] = [e.lngLat.lng, e.lngLat.lat];
    if (dragVertex === 0) ring[ring.length - 1] = ring[0];
    if (pending) pending.feature.geometry.coordinates = [ring];
    showVertexHandles();
    refreshBoxes();
  });
  map.on("mouseup", function () {
    if (dragVertex == null) return;
    dragVertex = null;
    map.dragPan.enable();
    map.getCanvas().style.cursor = "";
    suppressClick = true;
    setTimeout(function () { suppressClick = false; }, 0);
    // Re-derive the selection for the new shape, keeping the user's picks.
    if (editingEdit && pending) {
      editingEdit.presetActions = Object.assign({}, pending.actions);
      pending.points.forEach(function (p) { setState(p.id, null); });
      var ring = editingEdit.ring;
      closeInspector();
      selectInRing(ring);
    }
  });
  map.on("dblclick", function (e) {
    if (!editMode || editTool !== "polygon" || pending) return;
    e.preventDefault();
    if (polyVerts.length >= 2) {
      var a = map.project(polyVerts[polyVerts.length - 1]),
          b = map.project(polyVerts[polyVerts.length - 2]);
      if (Math.hypot(a.x - b.x, a.y - b.y) < 3) polyVerts.pop();
    }
    closePolygon();
  });
  document.addEventListener("keydown", function (e) {
    if (!editMode || editTool !== "polygon") return;
    if (e.key === "Escape") cancelPolyDraw();
    else if (e.key === "Enter") closePolygon();
  });

  // ------------------------------------------------- the per-tech inspector
  // The drawn area groups its served points by technology; each technology
  // gets a verb: leave / exclude / plan:<id>. (The design's EditInspector.)
  var inspectorEl = document.getElementById("edit-inspector");

  function recolorPending() {
    pending.points.forEach(function (p) {
      var acted = 0;
      p.coveredBy.forEach(function (cov) {
        var t = nameToTech[cov];
        var a = pending.actions[t];
        if (a && a !== "leave") acted++;
      });
      setState(p.id, acted === 0 ? "selected" : acted === p.coveredBy.length ? "full" : "partial");
    });
  }

  function openInspector(feature, points) {
    var perTech = {};
    points.forEach(function (p) {
      p.coveredBy.forEach(function (cov) {
        var t = nameToTech[cov];
        if (t == null) return;
        perTech[t] = (perTech[t] || 0) + 1;
      });
    });
    pending = { feature: feature, points: points, actions: {} };
    if (editingEdit) pending.actions = Object.assign({}, editingEdit.presetActions);
    recolorPending();
    refreshBoxes();

    var html = editingEdit
      ? '<b style="font-size:14px">Editing saved edit · <span class="num">' + points.length +
        '</span> locations</b><div style="font-size:12px;color:var(--muted);margin-top:2px">change the picks below, redraw the shape, or delete it</div>'
      : '<b style="font-size:14px">Drawn area · <span class="num">' + points.length +
        "</span> locations</b>";
    Object.keys(perTech).sort().forEach(function (t) {
      var name = (config.techNames || {})[t] || t;
      var color = (config.techColors || {})[t] || "#565EC1";
      var current = pending.actions[t] || "leave";
      html += '<div style="margin-top:10px"><div style="font-size:12.5px;font-weight:600;margin-bottom:4px">' +
        '<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:' + color +
        ';margin-right:6px"></span>' + name + " (" + t + ') <span style="color:var(--muted);font-weight:500">· serves <span class="num">' +
        perTech[t] + "</span> here</span></div>" +
        '<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center" data-tech-verbs="' + t + '">' +
        '<span class="chip click ' + (current === "leave" ? "accent" : "ghost") + '" data-verb="leave">leave</span>' +
        '<span class="chip click ' + (current === "exclude" ? "accent" : "ghost") + '" data-verb="exclude">exclude</span>';
      // A plan picker only when there's an actual choice: with one plan the
      // tech default already applies, so "set plan" would be a no-op. (An
      // existing set-plan pick always shows, so it can be seen and unset.)
      var techPlans = (config.plansByTech || {})[t] || [];
      if (techPlans.length > 1 || current.indexOf("plan:") === 0) {
        html += '<select class="sel" data-plan-select style="font-size:12px;padding:2px 6px;max-width:150px">' +
          '<option value="">set plan…</option>';
        techPlans.forEach(function (pl) {
          html += '<option value="plan:' + pl.id + '"' +
            (current === "plan:" + pl.id ? " selected" : "") + ">" + pl.name + "</option>";
        });
        html += "</select>";
      }
      html += "</div></div>";
    });
    if (editingEdit) {
      html += '<div style="font-size:11.5px;color:var(--muted);margin-top:10px">drag the white vertices on the map to reshape</div>' +
        '<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center">' +
        '<button class="btn danger-quiet sm" type="button" data-inspector-delete>Delete edit</button>' +
        '<span style="flex:1"></span>' +
        '<button class="btn sm" type="button" data-inspector-cancel>Cancel</button>' +
        '<button class="btn primary sm" type="button" data-inspector-save>Save changes</button></div>';
    } else {
      html += '<div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">' +
        '<button class="btn sm" type="button" data-inspector-cancel>Cancel</button>' +
        '<button class="btn primary sm" type="button" data-inspector-save>Save edit</button></div>';
    }
    inspectorEl.innerHTML = html;
    inspectorEl.style.display = "";

    inspectorEl.querySelectorAll("[data-tech-verbs]").forEach(function (grp) {
      grp.addEventListener("click", function (ev) {
        var chip = ev.target.closest("[data-verb]");
        if (!chip) return;
        grp.querySelectorAll("[data-verb]").forEach(function (c) {
          c.classList.remove("accent"); c.classList.add("ghost");
        });
        chip.classList.add("accent"); chip.classList.remove("ghost");
        var sel = grp.querySelector("[data-plan-select]");
        if (sel) sel.value = "";
        pending.actions[grp.getAttribute("data-tech-verbs")] = chip.getAttribute("data-verb");
        recolorPending();
      });
      var sel = grp.querySelector("[data-plan-select]");
      if (sel) sel.addEventListener("change", function () {
        grp.querySelectorAll("[data-verb]").forEach(function (c) {
          c.classList.remove("accent"); c.classList.add("ghost");
        });
        // Re-picking the placeholder is "leave".
        if (!sel.value) {
          var leave = grp.querySelector('[data-verb="leave"]');
          leave.classList.add("accent"); leave.classList.remove("ghost");
        }
        pending.actions[grp.getAttribute("data-tech-verbs")] = sel.value || "leave";
        recolorPending();
      });
    });
    inspectorEl.querySelector("[data-inspector-cancel]").addEventListener("click", cancelInspector);
    inspectorEl.querySelector("[data-inspector-save]").addEventListener("click", confirmInspector);
    var delBtn = inspectorEl.querySelector("[data-inspector-delete]");
    if (delBtn) delBtn.addEventListener("click", function () {
      var ee = editingEdit;
      cancelInspector();
      document.dispatchEvent(new CustomEvent("bdk:edit-remove",
        { detail: { editfileId: ee.id, name: ee.name } }));
    });
    showVertexHandles();
  }

  function closeInspector() {
    inspectorEl.style.display = "none";
    inspectorEl.innerHTML = "";
    pending = null;
    refreshBoxes();
    showVertexHandles();  // clears the handles once editingEdit is gone
  }
  function cancelInspector() {
    pending.points.forEach(function (p) { setState(p.id, null); });
    var wasEditing = editingEdit != null;
    editingEdit = null;
    closeInspector();
    if (wasEditing) say("Left the edit as it was.");
  }

  function confirmReplace() {
    // Save the modified saved-edit: same editfile, new shape/picks; the
    // server runs the full recompute so the old version's effect lifts.
    var markers = [];
    pending.points.forEach(function (p) {
      var byAction = {};
      p.coveredBy.forEach(function (cov) {
        var a = pending.actions[nameToTech[cov]];
        if (!a || a === "leave") return;
        (byAction[a] = byAction[a] || []).push(cov);
      });
      Object.keys(byAction).forEach(function (a) {
        var marker = { id: p.id, editedFile: byAction[a] };
        if (a.indexOf("plan:") === 0) marker.plan_id = Number(a.slice(5));
        markers.push(marker);
      });
    });
    if (!markers.length) {
      say("Every technology is set to leave — use Delete edit to remove it entirely.");
      return;
    }
    var ee = editingEdit;
    editingEdit = null;
    var feature = Object.assign({}, pending.feature, { properties: {} });
    // Swap the new shape into the saved-edit layer NOW (in place, same id) —
    // otherwise the old shape pops back until the recompute lands and reads
    // as a second polygon. A failed save re-fetches the server truth.
    persistedBoxes = persistedBoxes.map(function (f) {
      return f.properties && f.properties.editfileId === ee.id
        ? Object.assign({}, f, { geometry: feature.geometry })
        : f;
    });
    pending.points.forEach(function (p) { setState(p.id, null); });
    closeInspector();
    say("Saving changes…");
    fetch("/map/edit/" + ee.id + "/replace", {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, csrfHeader()),
      credentials: "include",
      body: JSON.stringify({ markers: markers, polygonfeature: feature }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok || res.d.status !== "success") throw new Error(res.d.message || "save failed");
        watchTask(res.d.task_id, "Recomputing", function (state) {
          if (state === "SUCCESS") {
            reloadTiles();
            refreshPersisted();
            say("Done ✓ — reload to refresh the edits list.");
          } else {
            refreshPersisted();
            say("The change didn't finish (" + state + ") — check the job tray.");
          }
        });
      })
      .catch(function (err) { refreshPersisted(); say("Error: " + err.message); });
  }

  function confirmInspector() {
    if (editingEdit) { confirmReplace(); return; }
    // One marker per (point, action): exclude markers carry editedFile only;
    // set-plan markers add plan_id. A point covered by two technologies with
    // different verbs gets two markers.
    var markers = [];
    pending.points.forEach(function (p) {
      var byAction = {};
      p.coveredBy.forEach(function (cov) {
        var a = pending.actions[nameToTech[cov]];
        if (!a || a === "leave") return;
        (byAction[a] = byAction[a] || []).push(cov);
      });
      var acted = 0;
      Object.keys(byAction).forEach(function (a) {
        acted += byAction[a].length;
        var marker = { id: p.id, editedFile: byAction[a] };
        if (a.indexOf("plan:") === 0) marker.plan_id = Number(a.slice(5));
        marker.st = acted === p.coveredBy.length ? "full" : "partial";
        markers.push(marker);
      });
      if (!acted) setState(p.id, null);
    });
    if (markers.length) {
      editBoxes.push({ feature: pending.feature, markers: markers });
      emitChanged();
      saveEdits();   // the design saves per drawn area
    }
    closeInspector();
  }

  function clearEdits() {
    editBoxes.forEach(function (b) { b.markers.forEach(function (m) { setState(m.id, null); }); });
    editBoxes = [];
    if (pending) cancelInspector();
    emitChanged();
  }

  function reloadTiles() {
    var src = map.getSource("custom");
    if (src && src.setTiles)
      src.setTiles([window.location.origin + config.tileUrl + "?v=" + Date.now()]);
  }
  function refreshPersisted() {
    fetch("/map/exclusions", { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.status === "success") { persistedBoxes = d.features; refreshBoxes(); }
      })
      .catch(function () {});
  }

  // ------------------------------------------------------------ save + SSE
  function csrfHeader() {
    var m = document.cookie.match(/(?:^|;\s*)csrf_access_token=([^;]+)/);
    return m ? { "X-CSRF-TOKEN": decodeURIComponent(m[1]) } : {};
  }
  function watchTask(taskId, label, onDone) {
    var es = new EventSource("/map/edit-events/" + taskId);
    es.addEventListener("state", function () { say(label + "…"); });
    es.addEventListener("done", function (ev) { es.close(); onDone(ev.data); });
    es.onerror = function () { es.close(); say("Connection lost — the job keeps running (watch the pill)."); };
  }

  function saveEdits() {
    if (!editBoxes.length) return;
    say("Saving edit…");
    fetch("/map/edit", {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, csrfHeader()),
      credentials: "include",
      body: JSON.stringify({
        folderid: config.folderId,
        markers: editBoxes.map(function (b) {
          return b.markers.map(function (m) {
            var out = { id: m.id, editedFile: m.editedFile };
            if (m.plan_id) out.plan_id = m.plan_id;
            return out;
          });
        }),
        polygonfeatures: editBoxes.map(function (b) {
          return Object.assign({}, b.feature, { properties: {} });
        }),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok || res.d.status !== "success") throw new Error(res.d.message || "edit failed");
        say("Saved — finalizing in the background…");
        watchTask(res.d.task_id, "Finalizing", function (state) {
          if (state === "SUCCESS") {
            persistedBoxes = persistedBoxes.concat(editBoxes.map(function (b) {
              return Object.assign({}, b.feature, { properties: {} });
            }));
            reloadTiles();
            clearEdits();
            refreshPersisted();
            say("Done ✓ — reload to see it in the edits list.");
          } else {
            say("The edit didn't finish (" + state + ") — check the job tray.");
          }
        });
      })
      .catch(function (err) { say("Error: " + err.message); });
  }

  function startEditOfEdit(editfileId) {
    // Load a saved edit into the inspector: zoom to its shape, rebuild its
    // selection (marker points included), and prefill its per-tech picks.
    if (config.readOnly) return;
    fetch("/map/edit/" + editfileId, { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.status !== "success") { say(d.message || "Couldn't load that edit."); return; }
        if (pending) cancelInspector();
        var ring = ringOfFeature(d.feature);
        if (!ring || ring.length < 4) { say("This edit's shape can't be read."); return; }
        editingEdit = {
          id: d.id, name: d.name, markers: d.markers || [],
          presetActions: actionsFromMarkers(d.markers), ring: ring,
        };
        say("Loading the edit…");
        window.BDKMap.setLocationsVisible(true);
        map.fitBounds(bboxOfRing(ring), { padding: 90, maxZoom: 17, duration: 400 });
        map.once("idle", function () {
          if (editingEdit && !pending) selectInRing(ring);
        });
      })
      .catch(function () { say("Couldn't load that edit."); });
  }

  // ------------------------------------------------------------ controller
  window.BDKMap = {
    editSavedEdit: startEditOfEdit,
    zoomToEdit: zoomToEdit,
    setTechVisible: function (tech, visible) {
      techLayerIds(Number(tech)).forEach(function (id) {
        if (map.getLayer(id))
          map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      });
    },
    setLocationsVisible: function (visible) {
      if (map.getLayer("locations"))
        map.setLayoutProperty("locations", "visibility", visible ? "visible" : "none");
    },
    setEditMode: function (on) { applyEditMode(on); },
    setEditTool: function (tool) { applyTool(tool); },
    flyTo: function (lng, lat) {
      map.flyTo({ center: [lng, lat], zoom: Math.max(map.getZoom(), 14) });
      new maplibregl.Popup({ closeButton: false, closeOnMove: true })
        .setLngLat([lng, lat]).setHTML("⌖").addTo(map);
    },
    finishRemove: function (editfileId) {
      persistedBoxes = persistedBoxes.filter(function (f) {
        return !(f.properties && f.properties.editfileId === editfileId);
      });
      reloadTiles();
      refreshBoxes();
    },
  };
  document.dispatchEvent(new CustomEvent("bdk:map-ready"));

  // ============================ page chrome ================================
  // (Plain DOM; talks to the island only through window.BDKMap + events.)

  document.querySelectorAll("[data-tech-toggle]").forEach(function (cb) {
    cb.addEventListener("change", function () {
      window.BDKMap.setTechVisible(cb.getAttribute("data-tech-toggle"), cb.checked);
    });
  });
  var locToggle = document.getElementById("locations-toggle");
  if (locToggle) locToggle.addEventListener("change", function () {
    window.BDKMap.setLocationsVisible(locToggle.checked);
  });

  // Browse | Draw
  var toolBrowse = document.getElementById("tool-browse");
  var toolDraw = document.getElementById("tool-draw");
  var drawTools = document.getElementById("draw-tools");
  function setTool(drawing) {
    if (!toolDraw) return;
    toolBrowse.classList.toggle("on", !drawing);
    toolDraw.classList.toggle("on", drawing);
    drawTools.style.display = drawing ? "" : "none";
    window.BDKMap.setEditMode(drawing);
  }
  if (toolBrowse) toolBrowse.addEventListener("click", function () { setTool(false); });
  if (toolDraw) toolDraw.addEventListener("click", function () {
    // Edits subtract from coverage — with nothing on the map yet, drawing has
    // nothing to act on. Say so instead of opening a dead-end mode.
    if (!(config.layers || []).length) {
      say("Nothing to edit yet — edits subtract from your coverage. Add network files first.");
      return;
    }
    setTool(true);
  });

  // edits list: show + edit + undo
  document.querySelectorAll("[data-show-edit]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      // Tight zoom to the shape itself (client-side bbox); the centroid
      // fetch only as a fallback for a shape not yet in the layer.
      if (window.BDKMap.zoomToEdit(Number(btn.getAttribute("data-show-edit")))) return;
      fetch("/api/get-edit-geojson-centroid/" + btn.getAttribute("data-show-edit"),
        { credentials: "include" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.latitude != null) window.BDKMap.flyTo(d.longitude, d.latitude);
        });
    });
  });
  function openEditForEditing(editfileId) {
    // Modifying a saved edit is NOT draw mode — no draw chrome, just the
    // inspector with the edit's picks and draggable vertices.
    setTool(false);
    window.BDKMap.editSavedEdit(editfileId);
  }
  document.querySelectorAll("[data-edit-edit]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openEditForEditing(Number(btn.getAttribute("data-edit-edit")));
    });
  });
  document.addEventListener("bdk:edit-open", function (e) {
    openEditForEditing(e.detail.editfileId);
  });
  function undoEdit(editfileId, name) {
    if (!confirm('Undo "' + (name || "this edit") + '"? Coverage recomputes without it.')) return;
    say("Undoing edit…");
    fetch("/api/delfiles", {
      method: "DELETE",
      headers: Object.assign({ "Content-Type": "application/json" }, csrfHeader()),
      credentials: "include",
      body: JSON.stringify({ file_ids: [], editfile_ids: [editfileId] }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok || res.d.status !== "success") throw new Error(res.d.message || "undo failed");
        watchTask(res.d.task_id, "Recomputing", function (state) {
          if (state === "SUCCESS") {
            window.BDKMap.finishRemove(editfileId);
            var row = document.querySelector('[data-editfile-row="' + editfileId + '"]');
            if (row) row.remove();
            say("Done ✓ — the affected locations are restored.");
          } else {
            say("The undo didn't finish (" + state + ") — check the job tray.");
          }
        });
      })
      .catch(function (err) { say("Error: " + err.message); });
  }
  document.querySelectorAll("[data-undo-edit]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      undoEdit(Number(btn.getAttribute("data-undo-edit")), btn.getAttribute("data-edit-name"));
    });
  });
  document.addEventListener("bdk:edit-remove", function (e) {
    var d = e.detail || {};
    if (d.editfileId == null) { say("That shape was just saved — one moment, then try again."); return; }
    undoEdit(d.editfileId, d.name);
  });

  // address search (fabric-powered)
  var searchInput = document.getElementById("addr-search");
  var searchResults = document.getElementById("addr-results");
  var searchTimer = null;
  function renderResults(rows) {
    if (!rows.length) {
      searchResults.innerHTML =
        '<div style="padding:9px 10px;font-size:12.5px;color:var(--muted)">No fabric address matches.</div>';
    } else {
      searchResults.innerHTML = rows.map(function (r, i) {
        var chip = !r.bsl ? '<span class="chip ghost">non-BSL</span>'
          : r.served ? '<span class="chip good">served</span>'
                     : '<span class="chip bad">not served</span>';
        return '<div class="srow" data-result="' + i + '"><span class="num" style="font-size:12.5px;flex:1">' +
          r.address + "</span>" + chip + "</div>";
      }).join("");
      searchResults.querySelectorAll("[data-result]").forEach(function (el) {
        el.addEventListener("click", function () {
          var r = rows[Number(el.getAttribute("data-result"))];
          if (r.longitude != null) window.BDKMap.flyTo(r.longitude, r.latitude);
          searchResults.style.display = "none";
        });
      });
    }
    searchResults.style.display = "";
  }
  if (searchInput && config.hasFabric) {
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimer);
      var q = searchInput.value.trim();
      if (q.length < 2) { searchResults.style.display = "none"; return; }
      searchTimer = setTimeout(function () {
        fetch("/api/address-search/" + config.folderId + "?query=" + encodeURIComponent(q),
          { credentials: "include" })
          .then(function (r) { return r.json(); })
          .then(function (d) { renderResults(d.results || d || []); })
          .catch(function () {});
      }, 250);
    });
  }

  // filed banner: reopen
  var reopenBtn = document.getElementById("map-reopen");
  if (reopenBtn) reopenBtn.addEventListener("click", function () {
    fetch("/submissions/reopen", {
      method: "POST", headers: csrfHeader(), credentials: "include",
    }).then(function () { window.location.reload(); });
  });
})();
