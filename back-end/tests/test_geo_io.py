"""Tests for the geo_io readers — the code most at risk from the geopandas/
pyogrio/fastkml modernization (KML folders-as-layers, GeoJSON, mixed geometry)."""

import pytest

from controllers.database_controller.geo_io import read_geo_bytes, suffix_for
from tests.conftest import SAMPLE_GEOJSON, SAMPLE_KML


def test_read_kml_concatenates_all_folders():
    gdf = read_geo_bytes(SAMPLE_KML, ".kml")
    # 2 folders, 3 placemarks total — must NOT be just the first folder/layer.
    assert len(gdf) == 3
    types = sorted(gdf.geom_type)
    assert types == ["LineString", "LineString", "Point"]


def test_read_kml_is_wgs84():
    gdf = read_geo_bytes(SAMPLE_KML, ".kml")
    assert gdf.crs is not None
    assert gdf.crs.to_epsg() == 4326


def test_read_geojson_polygon_and_point():
    gdf = read_geo_bytes(SAMPLE_GEOJSON, ".geojson")
    assert len(gdf) == 2
    assert set(gdf.geom_type) == {"Polygon", "Point"}


def test_read_accepts_str_and_bytes():
    from_bytes = read_geo_bytes(SAMPLE_GEOJSON, ".geojson")
    from_str = read_geo_bytes(SAMPLE_GEOJSON.decode("utf-8"), ".geojson")
    assert len(from_bytes) == len(from_str) == 2


def test_empty_input_returns_empty_frame():
    gdf = read_geo_bytes(b'{"type":"FeatureCollection","features":[]}', ".geojson")
    assert len(gdf) == 0


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("foo.kml", ".kml"),
        ("FOO.KML", ".kml"),
        ("bar.geojson", ".geojson"),
        ("baz.shp", ".shp"),
        ("noext", ".geojson"),
        (None, ".geojson"),
    ],
)
def test_suffix_for(filename, expected):
    assert suffix_for(filename) == expected
