"""The files & plans page (/files) — fabric, coverage, and plans tabs.

Pins, against the real services underneath (eager celery, tiles stubbed):
  - the geometry→technology guess on upload (lines → Fiber 50 wired,
    polygons → Unlicensed FW 70 wireless; unreadable files get a plain error;
    fabric CSVs are pointed at the Fabric tab);
  - the fabric tab (add/replace through intake v2, stats, the overridable
    vintage hard-warning);
  - the coverage table (rows, tech filter chips, same-geometry tech changes
    write through, cross-geometry changes hit the friction modal and then
    recompute, plan select with the blocked-at-export chip, the line-only
    buffer flow, remove);
  - the plans tab + modal (save/edit through plan_service, write-through to
    kml_data so late plan assignment still reaches the export);
  - org/filing scoping and CSRF on every page POST.
"""

import json
from datetime import date

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

LINES_GEOJSON = json.dumps(
    {
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
).encode()

POLYGON_GEOJSON = json.dumps(
    {
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
).encode()

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),
]


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


@pytest.fixture()
def no_tiles(monkeypatch):
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _login_with_filing(client, db_session, email, org_name=None):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=org_name or f"org-{email}")
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    folder = H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))
    return org, folder


def _seed_cov(
    db_session,
    folder,
    name="route.geojson",
    data=LINES_GEOJSON,
    ftype="wired",
    tech=50,
    compute=False,
):
    f = H.seed_coverage(db_session, folder.id, data, filename=name, filetype=ftype, techType=tech)
    if compute:  # needs fabric seeded first
        H.compute_coverage(db_session, folder.id, f)
    return f


# -------------------------------------------------------------- geometry guess


def test_guess_geometry_lines_polygons_and_garbage():
    from services.upload_service import guess_geometry

    assert guess_geometry("a.geojson", LINES_GEOJSON) == {
        "geom": "lines",
        "type": "wired",
        "techType": 50,
    }
    assert guess_geometry("b.geojson", POLYGON_GEOJSON) == {
        "geom": "polygons",
        "type": "wireless",
        "techType": 70,
    }
    assert guess_geometry("c.geojson", b"not geojson at all")["geom"] is None


# -------------------------------------------------------------- page rendering


def test_files_unauthenticated_redirects(client):
    resp = client.get("/files")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/auth/login")


def test_files_without_filing_explains(client, db_session):
    login_page_session(client, email="nofiling@example.com")
    html = client.get("/files").get_data(as_text=True)
    assert "No filing yet" in html


def test_coverage_tab_lists_files_and_filter_chips(client, db_session):
    org, folder = _login_with_filing(client, db_session, "cov@example.com")
    _seed_cov(db_session, folder)
    _seed_cov(
        db_session, folder, name="sector.geojson", data=POLYGON_GEOJSON, ftype="wireless", tech=70
    )

    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert "route.geojson" in html and "sector.geojson" in html
    assert "Fiber (50) · 1" in html and "Unlicensed FW (70) · 1" in html
    # geometry column derives from the compute type
    assert "lines" in html and "polygons" in html
    # no plans yet -> the add-a-plan affordance (readiness lives in the badge)
    assert "add a plan…" in html and "blocked at export" not in html

    filtered = client.get("/files?tab=coverage&tech=50").get_data(as_text=True)
    assert "route.geojson" in filtered and "sector.geojson" not in filtered


def test_coverage_tab_edit_rows_put_summary_in_the_wide_columns(client, db_session, no_tiles):
    """The edit's ✏ summary outgrows the filename column: the 'manual edit'
    chip sits there instead, and the summary spans technology+plan."""
    from services import edit_service

    org, folder = _login_with_filing(client, db_session, "editrow@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    cov = _seed_cov(
        db_session,
        folder,
        name="sector.geojson",
        data=POLYGON_GEOJSON,
        ftype="wireless",
        tech=70,
        compute=True,
    )
    u = _get_user(db_session, "editrow@example.com")
    edit_area = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-79.96, 37.27],
                    [-79.93, 37.27],
                    [-79.93, 37.29],
                    [-79.96, 37.29],
                    [-79.96, 37.27],
                ]
            ],
        },
    }
    edit_service.apply_edit(
        user_id=u.id,
        folderid=folder.id,
        markers=[[{"id": 1001, "editedFile": [cov.name]}]],
        polygonfeatures=[edit_area],
        session=db_session,
    )
    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert '<td><span class="chip ghost">manual edit</span></td>' in html
    assert 'colspan="2"' in html and "✏" in html
    assert html.index("manual edit") < html.index("✏")  # chip first, summary in the room


def test_fabric_tab_states(client, db_session):
    org, folder = _login_with_filing(client, db_session, "fab@example.com")
    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert "Add the fabric" in html

    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert "test_fabric.csv" in html
    assert "Replace…" in html
    assert "locations" in html  # stat blocks


# -------------------------------------------------------------- fabric intake


def test_fabric_upload_ingests(client, db_session, no_tiles):
    from database.models import fabric_data

    org, folder = _login_with_filing(client, db_session, "fabup@example.com")
    csv_bytes = make_active_fabric_csv(FABRIC_ROWS)
    resp = client.post(
        "/files/fabric/upload",
        data={
            "fabric_file": (__import__("io").BytesIO(csv_bytes), "FCC_Active_BSL_06302025_ver7.csv")
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(fabric_data).count() == 2


def test_fabric_upload_wrong_vintage_warns_then_overrides(client, db_session, no_tiles):
    import io

    from database.models import fabric_data

    org, folder = _login_with_filing(client, db_session, "fabwarn@example.com")
    # Deadline 2025-09 (June 2025 window) expects data-as-of 12/31/2024; this
    # delivery is a year older.
    csv_bytes = make_active_fabric_csv(FABRIC_ROWS)
    resp = client.post(
        "/files/fabric/upload",
        data={"fabric_file": (io.BytesIO(csv_bytes), "FCC_Active_BSL_12312023_ver6.csv")},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    assert "Use anyway" in body
    # "Use anyway" re-submits the still-filled upload form. htmx only puts a
    # file input into the request when the requesting element is multipart,
    # so the button must carry hx-encoding or the override arrives fileless.
    assert 'hx-include="#fabric-upload-form"' in body
    assert 'hx-encoding="multipart/form-data"' in body
    db_session.expire_all()
    assert db_session.query(fabric_data).count() == 0  # nothing ingested yet

    resp = client.post(
        "/files/fabric/upload",
        data={
            "fabric_file": (io.BytesIO(csv_bytes), "FCC_Active_BSL_12312023_ver6.csv"),
            "override": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(fabric_data).count() == 2

    # An overridden wrong-vintage fabric wears a RED "wrong version" chip on
    # the tab afterwards (allowed, but loud — not the soft warn chip).
    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert "wrong version" in html
    assert 'class="chip bad"' in html


def test_carried_banner_needs_real_lineage(client, db_session):
    """The carried-over banner means CARRIED (folder lineage set) — a fresh
    filing with network files uploaded before the fabric is the normal
    either-order setup, not a carry-forward."""
    org, folder = _login_with_filing(client, db_session, "carrybanner@example.com")
    _seed_cov(db_session, folder)  # files, no fabric, NO lineage

    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert "Everything carried over" not in html

    # A real carry-forward (lineage set) DOES get the welcome.
    folder.source_folder_id = folder.id  # any non-null lineage works for the render
    db_session.commit()
    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert "Everything carried over" in html


# -------------------------------------------------------------- coverage upload


def test_coverage_upload_applies_geometry_guess(client, db_session, no_tiles):
    import io

    from database.models import file as file_model

    org, folder = _login_with_filing(client, db_session, "covup@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    resp = client.post(
        "/files/coverage/upload",
        data={
            "network_files": [
                (io.BytesIO(LINES_GEOJSON), "mainline_routes.geojson"),
                (io.BytesIO(POLYGON_GEOJSON), "sector_coverage.geojson"),
            ]
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    db_session.expire_all()
    by_name = {
        f.name: f
        for f in db_session.query(file_model).filter(file_model.folder_id == folder.id)
        if f.type in ("wired", "wireless")
    }
    assert by_name["mainline_routes.geojson"].type == "wired"
    assert by_name["mainline_routes.geojson"].techType == 50
    assert by_name["sector_coverage.geojson"].type == "wireless"
    assert by_name["sector_coverage.geojson"].techType == 70


def test_coverage_upload_deduplicates_filenames(client, db_session, no_tiles):
    """REGRESSION: filenames are load-bearing keys (tiles' network_coverages,
    edit markers' editedFile, map layer ids, get_file_with_name) — two files
    in one filing must never share a name. Uploading the same file again
    stores it as 'name (2).ext', including within a single batch."""
    import io

    from database.models import file as file_model

    org, folder = _login_with_filing(client, db_session, "covdup@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    for _ in range(2):
        client.post(
            "/files/coverage/upload",
            data={"network_files": [(io.BytesIO(POLYGON_GEOJSON), "sector.geojson")]},
            content_type="multipart/form-data",
        )
    # And a batch containing the same name twice more.
    client.post(
        "/files/coverage/upload",
        data={
            "network_files": [
                (io.BytesIO(POLYGON_GEOJSON), "sector.geojson"),
                (io.BytesIO(POLYGON_GEOJSON), "sector.geojson"),
            ]
        },
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    names = sorted(
        f.name
        for f in db_session.query(file_model).filter(
            file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless"))
        )
    )
    assert names == [
        "sector (2).geojson",
        "sector (3).geojson",
        "sector (4).geojson",
        "sector.geojson",
    ]


def test_upload_after_default_plan_inherits_its_speeds(client, db_session, no_tiles):
    """A file uploaded AFTER its tech's default plan exists computes with the
    plan's speeds, not the upload's 0/0 placeholders — and the
    export (which reads kml_data) carries them."""
    import io

    from database.models import file as file_model
    from database.models import kml_data
    from services import export_service, plan_service

    org, folder = _login_with_filing(client, db_session, "covplan@example.com")
    org.provider_id = 330054
    db_session.commit()
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    plan_service.save_plan(folder.id, "Gig Fiber", 50, 1000, 500, db_session, is_default=True)
    client.post(
        "/files/coverage/upload",
        data={"network_files": [(io.BytesIO(LINES_GEOJSON), "route.geojson")]},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    f = (
        db_session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type == "wired")
        .one()
    )
    assert (f.maxDownloadSpeed, f.maxUploadSpeed) == (1000, 500)
    rows = db_session.query(kml_data).filter(kml_data.file_id == f.id).all()
    assert rows and all(r.maxDownloadSpeed == 1000 for r in rows)

    u = _get_user(db_session, "covplan@example.com")
    csv_out, _ = export_service.export_filing(
        user_id=u.id, folderid=folder.id, session=db_session, snapshot_inline=True
    )
    assert b"1000" in csv_out.getvalue() and b"500" in csv_out.getvalue()


def test_coverage_upload_rejects_csv_and_garbage(client, db_session):
    import io

    org, folder = _login_with_filing(client, db_session, "covbad@example.com")
    resp = client.post(
        "/files/coverage/upload",
        data={"network_files": (io.BytesIO(b"id,addr\n1,x"), "fabric.csv")},
        content_type="multipart/form-data",
    )
    assert "Fabric tab" in resp.get_data(as_text=True)

    resp = client.post(
        "/files/coverage/upload",
        data={"network_files": (io.BytesIO(b"garbage"), "what.geojson")},
        content_type="multipart/form-data",
    )
    assert "as coverage geometry" in resp.get_data(as_text=True)


# -------------------------------------------------------------- tech changes


def test_tech_change_same_geometry_writes_through(client, db_session):
    from database.models import kml_data

    org, folder = _login_with_filing(client, db_session, "tech1@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder, compute=True)

    resp = client.post(f"/files/coverage/{f.id}/tech", data={"tech": "40"})
    assert resp.status_code == 200
    db_session.expire_all()
    assert f.techType == 40
    assert f.type == "wired"  # same family, no recompute needed
    rows = db_session.query(kml_data).filter(kml_data.file_id == f.id).all()
    assert rows and all(r.techType == 40 for r in rows)


def test_tech_change_cross_geometry_frictions_then_recomputes(client, db_session, no_tiles):
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "tech2@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder)  # wired lines file

    resp = client.post(f"/files/coverage/{f.id}/tech", data={"tech": "70"})
    body = resp.get_data(as_text=True)
    assert "Change technology?" in body  # the friction modal, not applied
    db_session.expire_all()
    assert f.techType == 50 and f.type == "wired"

    resp = client.post(f"/files/coverage/{f.id}/tech", data={"tech": "70", "confirm": "1"})
    assert resp.status_code == 200
    db_session.expire_all()
    assert f.techType == 70 and f.type == "wireless"
    assert (
        db_session.query(celerytaskinfo).filter(celerytaskinfo.operation_type == "Update").count()
        == 1
    )


def test_tech_change_restamps_from_new_techs_default(client, db_session):
    """Changing an unassigned file's tech re-resolves its governing plan: the
    NEW tech's default stamps the file and its kml rows (the old tech's
    numbers must not ride along into the export)."""
    from database.models import file as file_model
    from database.models import kml_data
    from services import plan_service

    org, folder = _login_with_filing(client, db_session, "techstamp@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder, compute=True)  # wired Fiber 50
    plan_service.save_plan(folder.id, "Fiber 100", 50, 100, 100, db_session, is_default=True)
    plan_service.save_plan(folder.id, "Cable 300", 40, 300, 30, db_session, is_default=True)
    db_session.expire_all()
    assert f.maxDownloadSpeed == 100

    resp = client.post(f"/files/coverage/{f.id}/tech", data={"tech": "40"})
    assert resp.status_code == 200
    db_session.expire_all()
    f = db_session.query(file_model).filter_by(id=f.id).one()
    assert f.techType == 40
    assert (f.maxDownloadSpeed, f.maxUploadSpeed) == (300, 30)
    rows = db_session.query(kml_data).filter(kml_data.file_id == f.id).all()
    assert rows and all(r.maxDownloadSpeed == 300 and r.techType == 40 for r in rows)


def test_tech_change_other_orgs_file_is_invisible(client, db_session):
    org, folder = _login_with_filing(client, db_session, "tech3@example.com")
    other = H.make_org(db_session, name="other-tech")
    other_folder = H.make_folder(db_session, other.id)
    other_file = H.seed_coverage(
        db_session,
        other_folder.id,
        LINES_GEOJSON,
        filename="theirs.geojson",
        filetype="wired",
        techType=50,
    )
    resp = client.post(f"/files/coverage/{other_file.id}/tech", data={"tech": "40"})
    assert resp.status_code == 302  # bounced, not found in MY filing
    db_session.expire_all()
    assert other_file.techType == 50


# -------------------------------------------------------------- plans


def test_plan_save_assign_and_write_through_to_kml(client, db_session):
    from database.models import kml_data, service_plan

    org, folder = _login_with_filing(client, db_session, "plan1@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder, compute=True)  # computed BEFORE the plan exists

    resp = client.post(
        "/files/plans/save",
        data={
            "tech": "50",
            "is_default": "on",
            "name": "Gig Fiber",
            "down": "1000",
            "up": "1000",
            "low_latency": "on",
            "category": "X",
            "use_default_brand": "on",
            "return_tab": "plans",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("HX-Redirect") == "/files?tab=plans"
    db_session.expire_all()
    plan = db_session.query(service_plan).one()
    assert plan.is_default and plan.tech_code == 50

    # Assign it explicitly to the file: the already-computed kml rows get the
    # plan's values without a recompute (the export reads kml_data).
    resp = client.post(f"/files/coverage/{f.id}/plan", data={"plan_id": str(plan.id)})
    assert resp.status_code == 200
    db_session.expire_all()
    assert f.plan_id == plan.id
    rows = db_session.query(kml_data).filter(kml_data.file_id == f.id).all()
    assert rows and all(r.maxDownloadSpeed == 1000 for r in rows)

    # With a default plan in place the add-a-plan nudge is gone.
    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert "add a plan…" not in html


def test_plan_modal_renders_and_invalid_save_reshows_with_error(client, db_session):
    org, folder = _login_with_filing(client, db_session, "plan2@example.com")
    _seed_cov(db_session, folder)

    html = client.get("/files/modals/plan?tech=50&return_tab=plans").get_data(as_text=True)
    assert "New plan" in html
    assert "Low-latency service" in html
    assert "Use default brand name" in html
    # The name is optional — a blank one self-names from tech + speeds.
    assert "(optional" in html
    # The default brand rides a data attribute — inlining it into the
    # onchange string truncated the handler (quotes inside a quoted
    # attribute) and made unchecking do nothing.
    assert 'data-default-brand="' in html
    assert 'b.value=this.checked ? "' not in html

    resp = client.post(
        "/files/plans/save",
        data={"tech": "50", "name": "", "down": "0", "up": "0", "return_tab": "plans"},
    )
    body = resp.get_data(as_text=True)
    assert "Speeds must be positive integers" in body
    assert resp.headers.get("HX-Redirect") is None

    # A nameless save with valid speeds lands as "<Tech> <down>/<up>".
    from database.models import service_plan

    client.post(
        "/files/plans/save",
        data={
            "tech": "50",
            "name": "",
            "down": "100",
            "up": "10",
            "low_latency": "on",
            "category": "X",
            "use_default_brand": "on",
            "return_tab": "plans",
        },
    )
    db_session.expire_all()
    assert db_session.query(service_plan).one().name == "Fiber 100/10"


def test_plan_modal_tech_is_selectable_and_save_honors_it(client, db_session):
    """Technology is a plan attribute picked in the modal (a select), with the
    'Set as default' checkbox beside it. ?tech= preselects (the coverage-tab
    nudges pass it); the save uses whatever the form says."""
    from database.models import service_plan

    org, folder = _login_with_filing(client, db_session, "plantech@example.com")
    _seed_cov(db_session, folder)

    html = client.get("/files/modals/plan?tech=50&return_tab=plans").get_data(as_text=True)
    assert 'name="tech"' in html and "<select" in html
    assert 'value="50" selected' in html
    assert "Set as default" in html
    # The old fixed-tech copy is gone.
    assert "Default for all" not in html

    # No ?tech at all still renders (the global "+ another plan" button).
    html = client.get("/files/modals/plan?return_tab=plans").get_data(as_text=True)
    assert 'name="tech"' in html

    client.post(
        "/files/plans/save",
        data={
            "tech": "40",
            "name": "Cable 300",
            "down": "300",
            "up": "30",
            "low_latency": "on",
            "category": "X",
            "use_default_brand": "on",
            "is_default": "on",
            "return_tab": "plans",
        },
    )
    db_session.expire_all()
    plan = db_session.query(service_plan).one()
    assert plan.tech_code == 40 and plan.is_default


def test_plans_tab_is_a_flat_list_with_tech_default_chip(client, db_session):
    """Plans render as ONE list (tech is an attribute, not the grouping),
    sorted by technology, defaults wearing a 'tech default' chip — and the
    'applies to every …' explainer is gone."""
    from services import plan_service

    org, folder = _login_with_filing(client, db_session, "planflat@example.com")
    _seed_cov(db_session, folder)  # fiber coverage
    plan_service.save_plan(folder.id, "Gig Fiber", 50, 1000, 1000, db_session, is_default=True)
    plan_service.save_plan(folder.id, "Future Cable", 40, 300, 30, db_session, is_default=True)

    html = client.get("/files?tab=plans").get_data(as_text=True)
    assert "tech default" in html
    assert "applies to every" not in html
    assert html.count("+ another plan") == 1
    # Sorted by tech: Cable (40) rows come before Fiber (50).
    assert html.index("Future Cable") < html.index("Gig Fiber")


def test_plans_tab_shows_missing_default_warning(client, db_session):
    org, folder = _login_with_filing(client, db_session, "plan3@example.com")
    _seed_cov(db_session, folder)
    html = client.get("/files?tab=plans").get_data(as_text=True)
    assert "no default Fiber plan — needed to export" in html
    assert "+ another plan" in html


# -------------------------------------------------------------- buffer


def test_buffer_modal_and_change_recomputes(client, db_session, no_tiles):
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "buf1@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder)

    html = client.get(f"/files/modals/buffer/{f.id}").get_data(as_text=True)
    assert "Coverage buffer" in html and "100 m" in html

    resp = client.post(f"/files/coverage/{f.id}/buffer", data={"buffer_m": "200"})
    assert resp.status_code == 200
    db_session.expire_all()
    assert f.coverage_buffer_m == 200
    assert db_session.query(celerytaskinfo).count() == 1

    # Re-applying the same value is a no-op (no second recompute).
    client.post(f"/files/coverage/{f.id}/buffer", data={"buffer_m": "200"})
    assert db_session.query(celerytaskinfo).count() == 1

    # Out-of-range values are ignored.
    client.post(f"/files/coverage/{f.id}/buffer", data={"buffer_m": "9999"})
    db_session.expire_all()
    assert f.coverage_buffer_m == 200


def test_buffer_is_wired_only(client, db_session):
    org, folder = _login_with_filing(client, db_session, "buf2@example.com")
    f = _seed_cov(
        db_session, folder, name="sector.geojson", data=POLYGON_GEOJSON, ftype="wireless", tech=70
    )
    assert client.get(f"/files/modals/buffer/{f.id}").status_code == 302
    assert (
        client.post(f"/files/coverage/{f.id}/buffer", data={"buffer_m": "200"}).status_code == 302
    )


# -------------------------------------------------------------- remove


def test_remove_file_dispatches_delete_chain(client, db_session, no_tiles):
    from database.models import celerytaskinfo
    from database.models import file as file_model

    org, folder = _login_with_filing(client, db_session, "rm1@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    f = _seed_cov(db_session, folder)
    fid = f.id

    resp = client.post(f"/files/coverage/{fid}/remove")
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(file_model).filter(file_model.id == fid).first() is None
    assert (
        db_session.query(celerytaskinfo).filter(celerytaskinfo.operation_type == "Delete").count()
        == 1
    )


# -------------------------------------------------------------- CSRF


def test_files_page_posts_require_csrf(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as plain:
        login_page_session(plain, email="csrf-files@example.com")
        org = H.make_org(db_session, name="csrf-files-org")
        u = _get_user(db_session, "csrf-files@example.com")
        u.organization_id = org.id
        db_session.commit()
        folder = H.make_folder(db_session, org.id)
        f = H.seed_coverage(
            db_session,
            folder.id,
            LINES_GEOJSON,
            filename="r.geojson",
            filetype="wired",
            techType=50,
        )
        resp = plain.post(f"/files/coverage/{f.id}/tech", data={"tech": "40"})
        assert resp.status_code == 302
        db_session.expire_all()
        assert f.techType == 50


def test_uploads_are_one_click_with_busy_feedback(client, db_session):
    """No bare file inputs: the styled button opens the picker, choosing a
    file submits (hx-trigger=change), and an Uploading… indicator shows while
    the request is in flight. An active job renders a processing chip."""
    org, folder = _login_with_filing(client, db_session, "oneclick@example.com")
    html = client.get("/files?tab=fabric").get_data(as_text=True)
    assert 'style="display:none"' in html  # the input is hidden
    assert 'hx-trigger="change"' in html  # picking a file submits
    assert "Uploading…" in html

    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert 'hx-trigger="change"' in html and "Uploading…" in html

    # An in-flight job shows as a chip on the tab.
    from datetime import datetime

    from database.models import celerytaskinfo

    db_session.add(
        celerytaskinfo(
            task_id="t-busy",
            status="PENDING",
            operation_type="Upload",
            operation_detail="Add more files to a filing",
            start_time=datetime.now(),
            user_email="oneclick@example.com",
            organization_id=org.id,
            folder_deadline=folder.deadline,
        )
    )
    db_session.commit()
    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert "Reading your files" in html


def test_plans_tab_shows_techs_without_coverage(client, db_session):
    """A plan may exist for a technology with no coverage yet: it still shows
    in the list (tech is just an attribute — any technology can be picked in
    the modal)."""
    from services import plan_service

    org, folder = _login_with_filing(client, db_session, "nocov@example.com")
    plan_service.save_plan(
        folder.id,
        name="Future Cable",
        tech_code=40,
        max_download=300,
        max_upload=30,
        session=db_session,
        is_default=True,
    )
    html = client.get("/files?tab=plans").get_data(as_text=True)
    assert "Cable (40)" in html and "Future Cable" in html
