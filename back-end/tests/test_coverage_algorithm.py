"""Characterization of the coverage *algorithms* on the modern geo stack.

These mirror exactly what kml_ops.compute_wired_locations /
compute_wireless_locations do geometrically (the functions themselves are
DB-coupled; full integration tests run in Docker against Postgres). The point is
to prove geopandas 1.x / shapely 2.x / pyproj produce correct results:
  - wired: BSLs within a 100 m buffer of a fiber LineString (buffer in EPSG:5070)
  - wireless: BSLs inside a coverage polygon (point-in-polygon)
  - the bsl_flag boolean-mask behavior the pipeline relies on
"""

from io import StringIO

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, Polygon

# 0.0001 deg latitude ~ 11.1 m, so these offsets are unambiguous vs a 100 m buffer.
FABRIC = pd.DataFrame(
    {
        "location_id": [1, 2, 3],
        "latitude": [46.4000, 46.4005, 46.4020],  # on-line, ~55 m, ~222 m
        "longitude": [-116.75, -116.75, -116.75],
        "bsl_flag": [True, True, True],
    }
)


def _fabric_points(df):
    return gpd.GeoDataFrame(
        df,
        crs="EPSG:4326",
        geometry=[Point(xy) for xy in zip(df.longitude, df.latitude)],
    )


def test_wired_100m_buffer_selects_near_points():
    fabric = _fabric_points(FABRIC)
    line = LineString([(-116.80, 46.40), (-116.70, 46.40)])
    fiber = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")

    buf = fiber.to_crs("EPSG:5070")
    buf["geometry"] = buf.buffer(100)  # 100 metres in an equal-area projection
    buf = buf.to_crs("EPSG:4326")

    served = set(gpd.sjoin(fabric, buf, how="inner").location_id)
    assert served == {1, 2}  # 3 (~222 m) is excluded


def test_wireless_point_in_polygon():
    fabric = _fabric_points(
        pd.DataFrame(
            {
                "location_id": [10, 11],
                "latitude": [46.45, 46.45],
                "longitude": [-116.75, -116.90],  # inside, outside
                "bsl_flag": [True, True],
            }
        )
    )
    poly = Polygon([(-116.80, 46.40), (-116.70, 46.40), (-116.70, 46.50), (-116.80, 46.50)])
    coverage = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326")

    served = set(gpd.sjoin(fabric, coverage, how="inner").location_id)
    assert served == {10}


def test_bsl_flag_parsed_as_bool_and_masks():
    """The pipeline reads fabric via pandas.read_csv and filters gdf[gdf['bsl_flag']].
    pandas must parse True/False as real booleans for that mask to work."""
    csv = "location_id,bsl_flag,latitude,longitude\n1,True,46.4,-116.7\n2,False,46.4,-116.7\n"
    df = pd.read_csv(StringIO(csv))
    assert df["bsl_flag"].dtype == bool
    assert set(df[df["bsl_flag"]].location_id) == {1}
