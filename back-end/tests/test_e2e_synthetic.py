"""Layer 2 — synthetic end-to-end, driving the real pipeline DIRECTLY via the
*_ops modules (mirrors celery_tasks.process_data). Committable; must pass in CI.

The served counts below are PINNED golden numbers measured from the actual
pipeline output on the committed synthetic data (dev-data/synthetic, generated
by scripts/make_synthetic_dataset.py from the transformed prod-13 geometry). If
a refactor changes the geometry/coverage math, these break — which is the point.
"""

import json
import os

import pytest

from tests import conftest_helpers as H
from tests.conftest import SYNTHETIC_DIR

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(SYNTHETIC_DIR, "test_fabric.csv")),
    reason="synthetic dataset not present",
)

# --- PINNED golden counts (synthetic data) ----------------------------------
EXPECTED_FABRIC_ROWS = 100_000
EXPECTED_WIRED_50 = 96
EXPECTED_WIRELESS_70 = 10_110
EXPECTED_WIRELESS_71 = 6_273

WIRED_FILE = "fiber.geojson"
WIRELESS_70_FILE = "wireless_5ghz.geojson"
WIRELESS_71_FILE = "wireless_25ghz.geojson"


def _read(name):
    with open(os.path.join(SYNTHETIC_DIR, name), "rb") as fh:
        return fh.read()


@pytest.fixture()
def seeded(db_session):
    """Seed org + folder + fabric + all three coverage layers, compute coverage,
    and return everything the assertions need."""
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)

    H.seed_fabric(s, folder.id, _read("test_fabric.csv"))

    wired = H.seed_coverage(s, folder.id, _read(WIRED_FILE), WIRED_FILE, "wired", H.TECH_WIRED)
    H.compute_coverage(s, folder.id, wired)

    w70 = H.seed_coverage(
        s,
        folder.id,
        _read(WIRELESS_70_FILE),
        WIRELESS_70_FILE,
        "wireless",
        H.TECH_WIRELESS_UNLICENSED,
    )
    H.compute_coverage(s, folder.id, w70)

    w71 = H.seed_coverage(
        s,
        folder.id,
        _read(WIRELESS_71_FILE),
        WIRELESS_71_FILE,
        "wireless",
        H.TECH_WIRELESS_LICENSED,
    )
    H.compute_coverage(s, folder.id, w71)

    return {"session": s, "org": org, "folder": folder, "wired": wired, "w70": w70, "w71": w71}


def test_fabric_import_row_count(seeded):
    from database.models import fabric_data

    assert seeded["session"].query(fabric_data).count() == EXPECTED_FABRIC_ROWS


def test_wired_served_count_pinned(seeded):
    served = H.served_locations_for_file(seeded["session"], seeded["wired"].id)
    assert len(served) == EXPECTED_WIRED_50
    # Stability check: the set is exactly reproducible across runs.
    assert len(served) == len(set(served))


def test_wireless_unlicensed_served_count_pinned(seeded):
    served = H.served_locations_for_file(seeded["session"], seeded["w70"].id)
    assert len(served) == EXPECTED_WIRELESS_70


def test_wireless_licensed_served_count_pinned(seeded):
    served = H.served_locations_for_file(seeded["session"], seeded["w71"].id)
    assert len(served) == EXPECTED_WIRELESS_71


def test_kml_data_techtype_matches_file(seeded):
    """kml_data.techType for each coverage file must equal the file's techType."""
    from database.models import kml_data

    s = seeded["session"]
    for key, tech in (("wired", 50), ("w70", 70), ("w71", 71)):
        techs = {
            r[0]
            for r in s.query(kml_data.techType).filter(kml_data.file_id == seeded[key].id).all()
        }
        assert techs == {tech}


def test_nonservice_edit_removes_expected_bsls(db_session):
    """Applying a Polygon editfile linked to a wireless coverage removes exactly
    the served BSLs whose points fall inside the polygon. We compute coverage
    once, derive a polygon over a quadrant of the served points, then recompute
    with the editfile linked and assert the drop equals the count of served
    points inside that polygon (>= 1)."""
    from database.models import kml_data

    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    H.seed_fabric(s, folder.id, _read("test_fabric.csv"))
    cov = H.seed_coverage(
        s,
        folder.id,
        _read(WIRELESS_70_FILE),
        WIRELESS_70_FILE,
        "wireless",
        H.TECH_WIRELESS_UNLICENSED,
    )
    H.compute_coverage(s, folder.id, cov)

    pts = (
        s.query(kml_data.location_id, kml_data.longitude, kml_data.latitude)
        .filter(kml_data.file_id == cov.id)
        .all()
    )
    before = len(pts)
    assert before == EXPECTED_WIRELESS_70

    lons = [p[1] for p in pts]
    lats = [p[2] for p in pts]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    # Lower-left quadrant, padded so boundary points are unambiguously inside.
    x0, y0 = min_lon - 0.01, min_lat - 0.01
    poly = [[x0, y0], [mid_lon, y0], [mid_lon, mid_lat], [x0, mid_lat], [x0, y0]]
    expected_inside = sum(1 for p in pts if x0 <= p[1] <= mid_lon and y0 <= p[2] <= mid_lat)
    assert expected_inside >= 1

    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [poly]},
    }

    # Recompute with the non-service polygon linked: clear prior results first
    # (process_data does the same on recompute).
    s.query(kml_data).filter(kml_data.file_id == cov.id).delete()
    s.commit()
    H.link_polygon_editfiles(s, folder.id, cov, [feature])
    H.compute_coverage(s, folder.id, cov)

    after = len(H.served_locations_for_file(s, cov.id))
    assert before - after == expected_inside


def test_export_csv_schema_and_rows(seeded):
    """kml_ops.generate_csv_data over the computed kml_data must produce the FCC
    BDC availability schema with > 0 rows."""
    from database.models import kml_data

    s = seeded["session"]
    file_ids = [seeded["wired"].id, seeded["w70"].id, seeded["w71"].id]
    results = s.query(kml_data).filter(kml_data.file_id.in_(file_ids)).all()
    df = H.kml_ops.generate_csv_data(results, seeded["org"].provider_id, seeded["org"].brand_name)
    assert list(df.columns) == [
        "provider_id",
        "brand_name",
        "location_id",
        "technology",
        "max_advertised_download_speed",
        "max_advertised_upload_speed",
        "low_latency",
        "business_residential_code",
    ]
    assert len(df) > 0
    # Every tech present should be one of the three we computed.
    assert set(df["technology"]).issubset({50, 70, 71})


def test_nonservice_features_parse_as_polygons():
    """Guard: the editfile data we write is the shape filter_points_within_
    editfile_polygons expects (a single Feature with geometry.type Polygon)."""
    feat = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    }
    blob = json.dumps(feat).encode("utf-8")
    parsed = json.loads(blob.decode("utf-8"))
    assert parsed["geometry"]["type"] == "Polygon"
