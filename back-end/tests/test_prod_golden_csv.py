"""Layer 4b — PROD golden for the EXPORT CSV: replay real production filings
and assert the availability CSV our export path generates matches the bytes
prod actually stored (the BDC report the provider filed).

This pins the export-layer behavior that kml_data equality cannot see. The
shipped default reports every (location, technology) claim the BDC will
accept: claims under multiple technologies may coexist at a location, but at
most one fixed-wireless claim (tech 70/71/72) survives — the fastest — since
the BDC rejects filings claiming two fixed-wireless technologies at one
location. The pinned reference exports were filed under that one-fixed-
wireless-row shape. (Earlier report-every-claim-era snapshots stay in the
fixture set as reference only — see csv-golden.json. The optional
export_max_service_only setting, pinned by unit tests in test_csv_export.py,
further collapses to a single row per location.)

References: prod-extract/<export_folder>/output/prod-stored-export.csv and
prod-extract/csv-golden.json, which maps each upload folder to the stored
export representing its filed CSV (fixtures are local-only, never committed).

Rows are compared as parsed CSV records, order-insensitively — physical row
order and quoting style are not part of the contract; field values are.
"""

import csv
import io
import json
import os

import pytest

from controllers.database_controller import kml_ops
from database.models import folder as folder_model
from database.models import organization as organization_model
from tests.conftest import REAL_DIR
from tests.test_prod_golden import _replay

PROD = os.path.join(REAL_DIR, "prod-extract")
MAPPING = os.path.join(PROD, "csv-golden.json")

pytestmark = [
    pytest.mark.golden,
    pytest.mark.realdata,
    pytest.mark.skipif(not os.path.isfile(MAPPING), reason="csv golden fixtures not present"),
]


def _cases():
    if not os.path.isfile(MAPPING):
        return []
    mapping = json.load(open(MAPPING))
    return [(int(fid), exp) for fid, exp in mapping.items() if not fid.startswith("_")]


def _rows(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    return rows[0], sorted(tuple(r) for r in rows[1:])


@pytest.mark.parametrize("fid,export_dir", _cases())
def test_export_csv_matches_prod_filed_bytes(db_session, fid, export_dir):
    s = db_session
    _replay(s, fid)
    org = s.query(organization_model).filter_by(name=f"org{fid}").one()
    folder = s.query(folder_model).filter_by(organization_id=org.id).one()

    out = kml_ops.export(
        folder.id,
        org.provider_id,
        org.brand_name,
        folder.deadline.strftime("%Y-%m-%d"),
        s,
        dispatch_copy=False,
    )
    ours_header, ours = _rows(out.getvalue())

    with open(os.path.join(PROD, export_dir, "output", "prod-stored-export.csv")) as fh:
        ref_header, ref = _rows(fh.read())

    assert ours_header == ref_header
    assert len(ours) == len(ref), (
        f"folder {fid}: {len(ours)} rows generated vs {len(ref)} rows prod filed "
        f"(export folder {export_dir})"
    )
    assert ours == ref, f"folder {fid}: CSV content diverges from prod's filed export"
