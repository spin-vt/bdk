"""Fabric intake v2 — ingestion routing, supplemental index, intake service.

The fabric model (back-end/docs/bdc-fabric-format.md): a delivery has up to
three roles — active (drives coverage), non_bsl
(stored + rendered, never exported as served), supplemental (address search
only). Coverage computation must consume exactly the active fabric; the other
two are stored beside it and must never leak into the pipeline.
"""

import json
from datetime import date

import pytest

from services.exceptions import ServiceError
from tests import conftest_helpers as H
from tests.conftest_helpers import make_active_fabric_csv, make_supplemental_csv

# A polygon over Roanoke; ACTIVE_INSIDE/NOBSL_INSIDE fall inside it.
COVERAGE_POLYGON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-80.01, 37.27],
                        [-79.90, 37.27],
                        [-79.90, 37.31],
                        [-80.01, 37.31],
                        [-80.01, 37.27],
                    ]
                ],
            },
        }
    ],
}

ACTIVE_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),  # inside coverage
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),  # outside coverage
]
NOBSL_ROWS = [
    (2001, "1 SCHOOL RD", "FALSE", 37.28, -79.94, "51161", "VA"),  # inside coverage
]
SUPP_ROWS = [
    (1001, "P", "1 MAIN ST"),
    (1001, "S", "ONE MAIN STREET REAR UNIT"),
    (1002, "S", "2 ELM AVENUE"),
]


def _seed_folder(s, deadline=None):
    org = H.make_org(s)
    folder = H.make_folder(s, org.id, deadline=deadline)
    return org, folder


def _make_fabric_file(s, folderid, csv_bytes, name, filetype, **kwargs):
    from controllers.database_controller import file_ops

    f = file_ops.create_file(
        filename=name, content=csv_bytes, folderid=folderid, filetype=filetype, session=s, **kwargs
    )
    s.commit()
    return f


# --- supplemental_ops: COPY ingestion into the search index ---------------------


def test_supplemental_write_to_db(db_session):
    from controllers.database_controller import supplemental_ops
    from database.models import supplemental_data

    s = db_session
    _, folder = _seed_folder(s)
    f = _make_fabric_file(
        s,
        folder.id,
        make_supplemental_csv(SUPP_ROWS),
        "FCC_Supplemental_12312025_rel_8.csv",
        "fabric_supplemental",
    )
    supplemental_ops.write_to_db(f.id)

    rows = s.query(supplemental_data).filter(supplemental_data.file_id == f.id).all()
    assert len(rows) == 3
    by_addr = {r.address: r for r in rows}
    rear = by_addr["ONE MAIN STREET REAR UNIT"]
    assert rear.location_id == 1001
    assert rear.primary_supplemental == "S"
    assert rear.zip_code == "24018"
    assert rear.state == "VA"


def test_supplemental_write_tolerates_pre_v6_column_name(db_session):
    """v1–v5 deliveries used `primary_secondary`; the index maps it onto the
    same column."""
    from controllers.database_controller import supplemental_ops
    from database.models import supplemental_data

    s = db_session
    _, folder = _seed_folder(s)
    legacy_csv = make_supplemental_csv(SUPP_ROWS).replace(
        b"primary_supplemental", b"primary_secondary"
    )
    f = _make_fabric_file(
        s, folder.id, legacy_csv, "FCC_Secondary_06302022_ver.csv", "fabric_supplemental"
    )
    supplemental_ops.write_to_db(f.id)

    rows = s.query(supplemental_data).filter(supplemental_data.file_id == f.id).all()
    assert sorted(r.primary_supplemental for r in rows) == ["P", "S", "S"]


def test_supplemental_write_rejects_non_supplemental_csv(db_session):
    from controllers.database_controller import supplemental_ops

    s = db_session
    _, folder = _seed_folder(s)
    f = _make_fabric_file(
        s, folder.id, make_active_fabric_csv(ACTIVE_ROWS), "renamed.csv", "fabric_supplemental"
    )
    with pytest.raises(ValueError):
        supplemental_ops.write_to_db(f.id)


# --- type-routed folder ingestion (the process_data CSV loop) -------------------


def test_write_folder_fabric_routes_by_type(db_session):
    from controllers.database_controller import fabric_ops
    from database.models import fabric_data, supplemental_data

    s = db_session
    _, folder = _seed_folder(s)
    active = _make_fabric_file(
        s,
        folder.id,
        make_active_fabric_csv(ACTIVE_ROWS),
        "FCC_Active_BSL_12312025_rel_8.csv",
        "fabric",
    )
    nobsl = _make_fabric_file(
        s,
        folder.id,
        make_active_fabric_csv(NOBSL_ROWS),
        "FCC_Active_NoBSL_12312025_rel_8.csv",
        "fabric_non_bsl",
    )
    supp = _make_fabric_file(
        s,
        folder.id,
        make_supplemental_csv(SUPP_ROWS),
        "FCC_Supplemental_12312025_rel_8.csv",
        "fabric_supplemental",
    )
    # An export-typed CSV (availability CSVs live in export folders) must be
    # left alone — it is not fabric.
    export = _make_fabric_file(s, folder.id, b"a,b\r\n1,2\r\n", "availability-x.csv", "export")

    fabric_ops.write_folder_fabric(folder.id, s)
    s.commit()  # process_data commits after the ingest step
    s.expire_all()

    active_locs = {r.location_id for r in s.query(fabric_data).filter_by(file_id=active.id)}
    nobsl_rows = s.query(fabric_data).filter_by(file_id=nobsl.id).all()
    assert active_locs == {1001, 1002}
    assert [r.location_id for r in nobsl_rows] == [2001]
    assert all(r.bsl_flag.upper() == "FALSE" for r in nobsl_rows)
    assert s.query(supplemental_data).filter_by(file_id=supp.id).count() == 3
    assert active.computed and nobsl.computed and supp.computed
    assert not export.computed


def test_write_folder_fabric_skips_computed_unless_reimport(db_session):
    from controllers.database_controller import fabric_ops
    from database.models import fabric_data

    s = db_session
    _, folder = _seed_folder(s)
    active = _make_fabric_file(
        s,
        folder.id,
        make_active_fabric_csv(ACTIVE_ROWS),
        "FCC_Active_BSL_12312025_rel_8.csv",
        "fabric",
    )
    fabric_ops.write_folder_fabric(folder.id, s)
    fabric_ops.write_folder_fabric(folder.id, s)  # second run: computed -> no-op
    assert s.query(fabric_data).filter_by(file_id=active.id).count() == 2


# --- coverage computation consumes exactly the active fabric --------------------


def test_compute_ignores_non_bsl_and_supplemental_files(db_session):
    """The selection regression fabric intake v2 exists to prevent: with non_bsl and
    supplemental CSVs sitting in the folder, coverage compute must read only
    the active fabric. (The legacy any-.csv selection would crash on the
    supplemental file — no latitude/longitude — and waste work on non-BSL.)"""
    from controllers.database_controller import fabric_ops

    s = db_session
    _, folder = _seed_folder(s)
    _make_fabric_file(
        s,
        folder.id,
        make_active_fabric_csv(ACTIVE_ROWS),
        "FCC_Active_BSL_12312025_rel_8.csv",
        "fabric",
    )
    _make_fabric_file(
        s,
        folder.id,
        make_active_fabric_csv(NOBSL_ROWS),
        "FCC_Active_NoBSL_12312025_rel_8.csv",
        "fabric_non_bsl",
    )
    _make_fabric_file(
        s,
        folder.id,
        make_supplemental_csv(SUPP_ROWS),
        "FCC_Supplemental_12312025_rel_8.csv",
        "fabric_supplemental",
    )
    fabric_ops.write_folder_fabric(folder.id, s)

    cov = H.seed_coverage(
        s,
        folder.id,
        json.dumps(COVERAGE_POLYGON).encode(),
        "wireless.geojson",
        "wireless",
        techType=70,
    )
    H.compute_coverage(s, folder.id, cov)

    served = H.served_locations_for_file(s, cov.id)
    assert served == {1001}  # the BSL active point inside coverage; never 2001


# --- fabric_service.intake_fabric -----------------------------------------------


def _intake_svc():
    from services import fabric_service

    return fabric_service


def _zip_of(members):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()


def _seed_user_folder(s, deadline=None):
    """An org + verified user + upload folder, ready for intake."""
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id)
    # Deadline near the December-2025 due date -> the window expects fabric v8.
    folder = H.make_folder(s, org.id, deadline=deadline or date(2026, 3, 2))
    return org, user, folder


V8_ZIP_MEMBERS = [
    ("FCC_Active_BSL_12312025_rel_8.csv", make_active_fabric_csv(ACTIVE_ROWS)),
    ("FCC_Active_NoBSL_12312025_rel_8.csv", make_active_fabric_csv(NOBSL_ROWS)),
    ("FCC_Supplemental_12312025_rel_8.csv", make_supplemental_csv(SUPP_ROWS)),
]


@pytest.fixture
def no_tiles(monkeypatch):
    """Intake dispatches the real op-4 recompute chain; keep the tippecanoe
    tile rebuild out of these unit tests (covered by smoke/golden)."""
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def test_intake_full_zip_classifies_and_ingests(db_session, no_tiles):
    from database.models import celerytaskinfo, supplemental_data
    from database.models import file as file_model

    s = db_session
    _, user, folder = _seed_user_folder(s)
    result = _intake_svc().intake_fabric(
        user.id, folder.id, "H5PKFG71-OPAQUE.zip", _zip_of(V8_ZIP_MEMBERS), s
    )

    s.expire_all()
    by_type = {f.type: f for f in s.query(file_model).filter_by(folder_id=folder.id)}
    assert set(by_type) == {"fabric", "fabric_non_bsl", "fabric_supplemental"}
    active = by_type["fabric"]
    assert active.fabric_data_as_of == date(2025, 12, 31)
    assert active.fabric_release == "8"
    assert active.computed  # eager celery ran the ingest
    assert s.query(supplemental_data).count() == 3
    assert result["vintage"]["matches"] is True
    assert result["task_id"]
    assert s.query(celerytaskinfo).filter_by(task_id=result["task_id"]).count() == 1


def test_intake_single_active_csv(db_session, no_tiles):
    from database.models import fabric_data

    s = db_session
    _, user, folder = _seed_user_folder(s)
    result = _intake_svc().intake_fabric(
        user.id,
        folder.id,
        "FCC_Active_BSL_12312025_rel_8.csv",
        make_active_fabric_csv(ACTIVE_ROWS),
        s,
    )
    assert result["roles"] == ["active"]
    assert s.query(fabric_data).count() == 2


def test_intake_vintage_mismatch_is_overridable(db_session, no_tiles):
    s = db_session
    _, user, folder = _seed_user_folder(s)  # window expects v8
    v6_csv = make_active_fabric_csv(ACTIVE_ROWS)

    with pytest.raises(ServiceError) as exc:
        _intake_svc().intake_fabric(
            user.id, folder.id, "FCC_Active_BSL_12312024_rel_6.csv", v6_csv, s
        )
    assert exc.value.status == 409
    assert "version 8" in exc.value.message and "December 2025" in exc.value.message

    result = _intake_svc().intake_fabric(
        user.id, folder.id, "FCC_Active_BSL_12312024_rel_6.csv", v6_csv, s, override_vintage=True
    )
    assert result["vintage"]["matches"] is False
    assert result["vintage"]["got_version"] == 6


def test_intake_rejects_unrecognizable_and_duplicate_roles(db_session, no_tiles):
    s = db_session
    _, user, folder = _seed_user_folder(s)
    svc = _intake_svc()

    with pytest.raises(ServiceError) as exc:
        svc.intake_fabric(user.id, folder.id, "notes.txt", b"hello", s)
    assert exc.value.status == 400

    two_actives = _zip_of(
        [
            ("FCC_Active_BSL_12312025_rel_8.csv", make_active_fabric_csv(ACTIVE_ROWS)),
            ("FCC_Active_BSL_12312025_rel_8_again.csv", make_active_fabric_csv(ACTIVE_ROWS)),
        ]
    )
    with pytest.raises(ServiceError) as exc:
        svc.intake_fabric(user.id, folder.id, "delivery.zip", two_actives, s)
    assert exc.value.status == 400


def test_intake_guards_org_filed_and_folder_type(db_session, no_tiles):
    s = db_session
    org, user, folder = _seed_user_folder(s)
    svc = _intake_svc()
    csv_bytes = make_active_fabric_csv(ACTIVE_ROWS)

    other_org = H.make_org(s, name="OtherOrg", provider_id=999)
    intruder = H.make_user(s, org_id=other_org.id, email="other@example.com")
    with pytest.raises(ServiceError):
        svc.intake_fabric(intruder.id, folder.id, "FCC_Active_BSL_12312025_rel_8.csv", csv_bytes, s)

    folder.status = "filed"
    s.commit()
    with pytest.raises(ServiceError) as exc:
        svc.intake_fabric(user.id, folder.id, "FCC_Active_BSL_12312025_rel_8.csv", csv_bytes, s)
    assert "filed" in exc.value.message.lower()
    folder.status = "open"

    export_folder = H.make_folder(s, org.id, name="Snapshot", ftype="export")
    with pytest.raises(ServiceError):
        svc.intake_fabric(
            user.id, export_folder.id, "FCC_Active_BSL_12312025_rel_8.csv", csv_bytes, s
        )


def test_fabric_replacement_recomputes_and_keeps_edits(db_session, no_tiles):
    """The fabric-replacement acceptance round-trip: replacing the fabric mid-filing
    recomputes coverage against the new fabric and re-applies existing edits
    exactly (markers), so a previously-excluded location stays excluded."""
    import json as _json

    from controllers.database_controller import editfile_ops, file_editfile_link_ops
    from database.models import fabric_data
    from database.models import file as file_model

    s = db_session
    _, user, folder = _seed_user_folder(s)

    # June-2025-era fabric: 1001 + 1004 inside coverage, both BSL.
    old_rows = [
        (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
        (1004, "4 OAK LN", "TRUE", 37.29, -79.93, "51161", "VA"),
    ]
    _intake_svc().intake_fabric(
        user.id,
        folder.id,
        "FCC_Active_BSL_12312024_rel_6.csv",
        make_active_fabric_csv(old_rows),
        s,
        override_vintage=True,
    )
    cov = H.seed_coverage(
        s, folder.id, json.dumps(COVERAGE_POLYGON).encode(), "cov.geojson", "wireless", techType=70
    )
    H.compute_coverage(s, folder.id, cov)
    assert H.served_locations_for_file(s, cov.id) == {1001, 1004}

    # The user excludes 1001 (an exact per-point marker edit).
    ef = editfile_ops.create_editfile(
        filename="edit_at_test",
        content=_json.dumps(COVERAGE_POLYGON["features"][0]).encode(),
        folderid=folder.id,
        session=s,
        markers=[{"id": 1001, "editedFile": ["cov.geojson"]}],
    )
    s.commit()
    file_editfile_link_ops.link_file_and_editfile(cov.id, ef.id, s)
    s.commit()
    from database.models import kml_data

    s.query(kml_data).filter(kml_data.location_id == 1001, kml_data.file_id == cov.id).delete()
    s.commit()
    assert H.served_locations_for_file(s, cov.id) == {1004}

    # Mid-filing replacement: v8 fabric — 1004 cycled out, 1003 is new.
    new_rows = [
        (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
        (1003, "3 NEW PL", "TRUE", 37.30, -79.92, "51161", "VA"),
    ]
    result = _intake_svc().intake_fabric(
        user.id,
        folder.id,
        "FCC_Active_BSL_12312025_rel_8.csv",
        make_active_fabric_csv(new_rows),
        s,
    )
    assert result["replaced"] == ["FCC_Active_BSL_12312024_rel_6.csv"]

    s.expire_all()
    fabric_files = s.query(file_model).filter_by(folder_id=folder.id, type="fabric").all()
    assert [f.name for f in fabric_files] == ["FCC_Active_BSL_12312025_rel_8.csv"]
    assert {r.location_id for r in s.query(fabric_data)} == {1001, 1003}
    # Recomputed against the new fabric, with the 1001 exclusion re-applied.
    assert H.served_locations_for_file(s, cov.id) == {1003}


# --- fabric_status + address search ---------------------------------------------


def test_fabric_status_reports_files_vintage_and_stats(db_session, no_tiles):
    s = db_session
    _, user, folder = _seed_user_folder(s)
    _intake_svc().intake_fabric(user.id, folder.id, "delivery.zip", _zip_of(V8_ZIP_MEMBERS), s)

    status = _intake_svc().fabric_status(user.id, folder.id, s)
    roles = {f["role"]: f for f in status["files"]}
    assert set(roles) == {"active", "non_bsl", "supplemental"}
    assert roles["active"]["data_as_of"] == "2025-12-31"
    assert roles["active"]["version"] == 8
    assert status["vintage"]["matches"] is True
    assert status["stats"] == {
        "locations": 3,  # 1001, 1002 active + 2001 non-BSL
        "bsl_locations": 2,
        "counties": 1,
        "states": 1,
        "supplemental_addresses": 3,
    }


def test_fabric_status_empty_folder(db_session):
    s = db_session
    _, user, folder = _seed_user_folder(s)
    status = _intake_svc().fabric_status(user.id, folder.id, s)
    assert status["files"] == []
    assert status["vintage"] is None
    assert status["stats"]["locations"] == 0


def test_search_addresses_over_fabric_and_supplemental(db_session, no_tiles):
    s = db_session
    _, user, folder = _seed_user_folder(s)
    _intake_svc().intake_fabric(user.id, folder.id, "delivery.zip", _zip_of(V8_ZIP_MEMBERS), s)
    cov = H.seed_coverage(
        s, folder.id, json.dumps(COVERAGE_POLYGON).encode(), "cov.geojson", "wireless", techType=70
    )
    H.compute_coverage(s, folder.id, cov)  # serves 1001 only

    # Primary-address hit, served chip on.
    hits = _intake_svc().search_addresses(user.id, folder.id, "main st", s)
    assert any(h["address"] == "1 MAIN ST" and h["served"] and h["bsl"] for h in hits)

    # Supplemental-only address resolves, inherits the location's coordinates
    # and served status from the fabric row.
    hits = _intake_svc().search_addresses(user.id, folder.id, "rear unit", s)
    assert len(hits) == 1
    h = hits[0]
    assert h["source"] == "supplemental"
    assert h["location_id"] == 1001
    assert h["latitude"] == pytest.approx(37.28)
    assert h["served"] is True

    # Non-BSL locations are searchable but flagged.
    hits = _intake_svc().search_addresses(user.id, folder.id, "school", s)
    assert len(hits) == 1
    assert hits[0]["bsl"] is False and hits[0]["served"] is False

    assert _intake_svc().search_addresses(user.id, folder.id, "zzz nowhere", s) == []
