"""Helpers for reading geospatial files (KML / GeoJSON) into GeoDataFrames.

This centralizes what used to be scattered, version-fragile reading code:
``fastkml`` for KML in ``vt_ops`` and ``fiona.drvsupport`` driver toggling in
``kml_ops``. Both are replaced by geopandas/pyogrio reads here.

KML stores placemarks inside nested ``<Folder>`` elements, which GDAL/pyogrio
exposes as separate *layers*. A naive single-layer ``read_file`` silently drops
geometry: one real fiber KML has 5 folders / 77 features, but a default read
returns only 2. So we always read and concatenate every layer.
"""

import os
import tempfile

import geopandas as gpd
import pandas as pd
import pyogrio


def read_geo_bytes(data, suffix):
    """Read geospatial ``bytes`` (or ``str``) into one GeoDataFrame.

    ``suffix`` must include the leading dot (e.g. ``".kml"``, ``".geojson"``) so
    GDAL can select the right driver. All layers are concatenated.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return _read_all_layers(path)
    finally:
        os.remove(path)


def _read_all_layers(path):
    try:
        layers = pyogrio.list_layers(path)
        layer_names = list(layers[:, 0]) if len(layers) else [None]
    except Exception:
        layer_names = [None]

    frames = []
    for name in layer_names:
        gdf = gpd.read_file(path, layer=name) if name is not None else gpd.read_file(path)
        if len(gdf):
            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    crs = next((f.crs for f in frames if f.crs is not None), "EPSG:4326")
    combined = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=crs)


def suffix_for(filename):
    """Return a driver-friendly file suffix (with leading dot) for a filename."""
    name = (filename or "").lower()
    if name.endswith(".kml"):
        return ".kml"
    if name.endswith(".geojson"):
        return ".geojson"
    _, ext = os.path.splitext(name)
    return ext or ".geojson"
