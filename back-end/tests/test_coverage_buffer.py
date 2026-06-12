"""Per-file coverage buffer (files & plans "advanced" setting).

A wired (line) coverage file can override how far from the route a location
counts as covered. The column is nullable and NULL means the pipeline's
longstanding 100 m default, so existing filings and files uploaded through the
SPA never change behavior (golden-guarded).
"""

import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

# A west-east line at lat 37.28. 0.0001 deg latitude ~ 11.1 m.
ROUTE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": [[-80.00, 37.28], [-79.95, 37.28]],
            },
        }
    ],
}

FABRIC_ROWS = [
    (1, "NEAR HOUSE", "TRUE", 37.28027, -79.97, "51161", "VA"),  # ~30 m north
    (2, "FAR HOUSE", "TRUE", 37.28135, -79.97, "51161", "VA"),  # ~150 m north
]


def _seed(db_session, buffer_m=None):
    org = H.make_org(db_session, name=f"BufOrg-{buffer_m}")
    folder = H.make_folder(db_session, org.id)
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    cov = H.seed_coverage(
        db_session,
        folder.id,
        json.dumps(ROUTE).encode(),
        filename="route.geojson",
        filetype="wired",
        techType=50,
    )
    if buffer_m is not None:
        cov.coverage_buffer_m = buffer_m
        db_session.commit()
    H.compute_coverage(db_session, folder.id, cov)
    return folder, cov


def test_null_buffer_keeps_the_100m_default(db_session):
    _, cov = _seed(db_session, buffer_m=None)
    assert H.served_locations_for_file(db_session, cov.id) == {1}


def test_wider_buffer_reaches_farther(db_session):
    _, cov = _seed(db_session, buffer_m=200)
    assert H.served_locations_for_file(db_session, cov.id) == {1, 2}


def test_narrower_buffer_excludes_near_misses(db_session):
    _, cov = _seed(db_session, buffer_m=25)
    assert H.served_locations_for_file(db_session, cov.id) == set()


def test_file_copy_carries_the_buffer(db_session):
    folder, cov = _seed(db_session, buffer_m=150)
    new_folder = H.make_folder(db_session, folder.organization_id, name="next")
    copied = cov.copy(db_session, export=False, new_folder_id=new_folder.id)
    db_session.commit()
    assert copied.coverage_buffer_m == 150
