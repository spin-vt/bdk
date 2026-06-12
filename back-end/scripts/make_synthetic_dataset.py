"""Generate the synthetic BDK test dataset (committable CI fixture).

Takes REAL coverage/fiber geometry from the prod extract and applies a single
shared affine transform (uniform scale + translate) so it overlays the
synthetic Roanoke, VA fabric footprint. One transform for all layers preserves
their spatial relationships.

Source geometry = the exact prod inputs of folder 13 (the validated golden
filing): the 5 GHz / 25 GHz wireless coverage KMLs and the fiber loop KMLs. The
transform throws away the real locations, so the OUTPUT (fake-location
geojson) is committable; the real inputs under dev-data/real-do-not-commit/ are
NEVER committed.

Tech mapping (matches the prod manifest):
  fiber loops      -> wired,    techType 50
  5 GHz coverage   -> wireless, techType 70 (unlicensed)
  2.5 GHz coverage -> wireless, techType 71 (licensed)

Run:  uv run python scripts/make_synthetic_dataset.py
"""

import glob
import os

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.affinity import scale, translate

# Allow the verification read below to load the (still sizeable) wireless polygons.
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD = os.path.join(REPO, "dev-data", "real-do-not-commit", "prod-extract", "13", "inputs")
SYNTH = os.path.join(REPO, "dev-data", "synthetic")
FRAC = 0.6  # fraction of the synthetic footprint the coverage should occupy
# The raw wireless polygons are ~150 MB of vertices — far too heavy to
# commit and they blow past GDAL's per-feature GeoJSON size limit. Simplify to a
# ~30 m tolerance: keeps the coverage footprint stable for a pinned served count
# while making the fixture lean and readable. (Exactness is the prod golden's
# job, not this synthetic CI fixture's.)
SIMPLIFY_M = 30.0


# The prod extract's wireless coverage KMLs, matched by band rather than by
# their (provider-identifying) literal filenames.
def _wireless_kml(band):
    matches = glob.glob(os.path.join(PROD, f"*_{band}_coverage_*.kml"))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {band} coverage KML in {PROD}, got {matches}")
    return os.path.basename(matches[0])


def read_all_layers(path):
    try:
        names = list(pyogrio.list_layers(path)[:, 0])
    except Exception:
        names = [None]
    frames = [gpd.read_file(path, layer=n) for n in names]
    frames = [f for f in frames if len(f)]
    crs = next((f.crs for f in frames if f.crs is not None), "EPSG:4326")
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=crs)
    return out.to_crs(4326)


def main():
    fabric = pd.read_csv(os.path.join(SYNTH, "test_fabric.csv"))
    sminx, sminy, smaxx, smaxy = (
        fabric.longitude.min(),
        fabric.latitude.min(),
        fabric.longitude.max(),
        fabric.latitude.max(),
    )
    # Center on the dense cluster (median point), not the bbox center, so the
    # thin fiber lines land where BSLs are dense enough to fall within 100 m.
    scx, scy = fabric.longitude.median(), fabric.latitude.median()

    # Load the real prod-13 layers.
    wireless_5ghz = _wireless_kml("5ghz")
    wireless_25ghz = _wireless_kml("25ghz")
    total = read_all_layers(os.path.join(PROD, wireless_5ghz))
    licensed = read_all_layers(os.path.join(PROD, wireless_25ghz))

    fiber_files = sorted(
        f
        for f in glob.glob(os.path.join(PROD, "*.kml"))
        if os.path.basename(f) not in (wireless_5ghz, wireless_25ghz)
    )
    fiber = pd.concat([read_all_layers(f) for f in fiber_files], ignore_index=True)
    fiber = gpd.GeoDataFrame(fiber, geometry="geometry", crs="EPSG:4326")
    fiber = fiber[fiber.geom_type.isin(["LineString", "MultiLineString"])]

    # Shared real bounds across all three layers.
    allbounds = pd.concat([total.bounds, licensed.bounds, fiber.bounds])
    rminx, rminy = allbounds.minx.min(), allbounds.miny.min()
    rmaxx, rmaxy = allbounds.maxx.max(), allbounds.maxy.max()
    rcx, rcy = (rminx + rmaxx) / 2, (rminy + rmaxy) / 2

    s = min(FRAC * (smaxx - sminx) / (rmaxx - rminx), FRAC * (smaxy - sminy) / (rmaxy - rminy))
    dx, dy = scx - rcx, scy - rcy

    def xform(geom):
        return translate(scale(geom, xfact=s, yfact=s, origin=(rcx, rcy)), xoff=dx, yoff=dy)

    for gdf, name in [
        (total, "wireless_5ghz"),
        (licensed, "wireless_25ghz"),
        (fiber, "fiber"),
    ]:
        out = gdf.copy()
        out["geometry"] = out.geometry.apply(xform)
        out = out.set_crs(4326, allow_override=True)
        # Simplify in a metric CRS (EPSG:5070) so the tolerance is in meters,
        # then return to 4326. preserve_topology keeps valid, non-collapsed
        # polygons. Fiber lines are already tiny; simplifying them is harmless.
        simp = out.to_crs(5070).geometry.simplify(SIMPLIFY_M, preserve_topology=True)
        out["geometry"] = gpd.GeoSeries(simp, crs=5070).to_crs(4326)
        # keep only the geometry column to keep files lean and avoid stray attrs
        out = out[["geometry"]]
        path = os.path.join(SYNTH, f"{name}.geojson")
        # 6-dp coordinate precision (~0.1 m) trims file size with no real loss.
        out.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=6)
        print(f"  wrote {name}.geojson: {len(out)} features, {os.path.getsize(path) // 1024} KB")

    # ---- verify overlap with the synthetic fabric ----
    pts = gpd.GeoDataFrame(
        fabric[["location_id"]],
        geometry=gpd.points_from_xy(fabric.longitude, fabric.latitude),
        crs="EPSG:4326",
    )
    t_out = gpd.read_file(os.path.join(SYNTH, "wireless_5ghz.geojson"))
    l_out = gpd.read_file(os.path.join(SYNTH, "wireless_25ghz.geojson"))
    f_out = gpd.read_file(os.path.join(SYNTH, "fiber.geojson"))

    in_total = set(gpd.sjoin(pts, t_out, predicate="within").location_id)
    in_lic = set(gpd.sjoin(pts, l_out, predicate="within").location_id)
    fbuf = f_out.to_crs(5070).buffer(100).to_crs(4326)
    near_fiber = set(
        gpd.sjoin(pts, gpd.GeoDataFrame(geometry=fbuf, crs=4326), predicate="within").location_id
    )
    served = in_total | in_lic | near_fiber

    print(f"\n  synthetic fabric BSLs: {len(pts)}")
    print(f"  within 5 GHz wireless (unlicensed): {len(in_total)}")
    print(f"  within 25 GHz licensed:             {len(in_lic)}")
    print(f"  within 100 m of fiber:              {len(near_fiber)}")
    print(f"  union served: {len(served)}  | unserved: {len(pts) - len(served)}")


if __name__ == "__main__":
    main()
