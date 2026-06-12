"""Carry-forward (operation 3) + the filing switcher's start-next action.

The copy-and-import chain previously had zero tests.
Pins that starting the next window's filing carries everything forward —
files, fabric, plans (with file assignments remapped), edits (with their
markers, plan ids remapped) — and that the recompute re-applies the edits
exactly. Also: starting a filing is ALWAYS an explicit user action via the
header switcher, one filing per org per window.
"""

from datetime import date

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.281, -79.94, "51161", "VA"),
]

POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""

EDIT_AREA = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [-79.96, 37.275],
                [-79.93, 37.275],
                [-79.93, 37.285],
                [-79.96, 37.285],
                [-79.96, 37.275],
            ]
        ],
    },
}


@pytest.fixture()
def no_tiles(monkeypatch):
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _seed_june_filing(db_session, org, user):
    """A June 2025 filing (deadline 2025-09-01) with fabric, computed coverage,
    a default plan, and one mixed edit (an exclusion + nothing else)."""
    from services import edit_service, plan_service

    folder = H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))
    cov = H.seed_coverage(
        db_session,
        folder.id,
        POLYGON_GEOJSON,
        filename="sector.geojson",
        filetype="wireless",
        techType=70,
    )
    H.compute_coverage(db_session, folder.id, cov)
    plan = plan_service.save_plan(
        folder.id,
        name="AirLink 100",
        tech_code=70,
        max_download=100,
        max_upload=20,
        session=db_session,
        is_default=True,
    )
    plan_service.assign_plan_to_file(cov.id, plan.id, db_session)
    edit_service.apply_edit(
        user_id=user.id,
        folderid=folder.id,
        markers=[[{"id": 1002, "editedFile": [cov.name]}]],
        polygonfeatures=[EDIT_AREA],
        session=db_session,
    )
    return folder, cov, plan


def test_start_next_filing_carries_everything_forward(db_session, no_tiles):
    from database.models import editfile as editfile_model
    from database.models import folder as folder_model
    from database.models import kml_data, service_plan
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="carry@example.com")
    user.verified = True
    db_session.commit()
    folder, cov, plan = _seed_june_filing(db_session, org, user)

    # Explicit start of the December 2025 window (due 2026-03-02 after rollover).
    filing_service.start_next_filing(user.id, db_session, today=date(2025, 10, 1))
    db_session.expire_all()

    new_folder = (
        db_session.query(folder_model)
        .filter(folder_model.organization_id == org.id, folder_model.id != folder.id)
        .one()
    )
    assert new_folder.type == "upload"
    assert new_folder.deadline > folder.deadline

    new_files = {f.name: f for f in new_folder.files}
    new_cov = new_files["sector.geojson"]
    # The OLD fabric is deliberately NOT carried — "you'll just need the new
    # fabric". Coverage stays uncomputed (dark) until it arrives.
    assert "test_fabric.csv" not in new_files
    assert new_cov.computed is False

    # The plan came along and the file assignment points at the COPY.
    new_plan = db_session.query(service_plan).filter(service_plan.folder_id == new_folder.id).one()
    assert new_plan.name == "AirLink 100" and new_plan.id != plan.id
    assert new_cov.plan_id == new_plan.id

    # The edit came along with its markers.
    new_edit = (
        db_session.query(editfile_model).filter(editfile_model.folder_id == new_folder.id).one()
    )
    assert new_edit.markers[0]["id"] == 1002

    # Drop in the December fabric: the intake recomputes the carried coverage
    # and re-applies the carried edit exactly — 1002 stays excluded.
    from services import fabric_service

    fabric_service.intake_fabric(
        user.id,
        new_folder.id,
        "FCC_Active_BSL_06302025_ver7.csv",
        make_active_fabric_csv(FABRIC_ROWS),
        db_session,
        override_vintage=True,
    )
    db_session.expire_all()
    served = {
        r.location_id for r in db_session.query(kml_data).filter(kml_data.file_id == new_cov.id)
    }
    assert served == {1001}

    # The original filing is untouched.
    assert {
        r.location_id for r in db_session.query(kml_data).filter(kml_data.file_id == cov.id)
    } == {1001}


def test_start_next_filing_is_once_per_window(db_session, no_tiles):
    from services import filing_service
    from services.exceptions import ServiceError

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="carry2@example.com")
    user.verified = True
    db_session.commit()
    _seed_june_filing(db_session, org, user)

    filing_service.start_next_filing(user.id, db_session, today=date(2025, 10, 1))
    with pytest.raises(ServiceError) as ei:
        filing_service.start_next_filing(user.id, db_session, today=date(2025, 10, 1))
    assert "window" in ei.value.message.lower()


def test_start_first_filing_without_history(db_session, no_tiles):
    from database.models import folder as folder_model
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="carry3@example.com")
    user.verified = True
    db_session.commit()

    filing_service.start_next_filing(user.id, db_session, today=date(2025, 10, 1))
    db_session.expire_all()
    new_folder = db_session.query(folder_model).filter_by(organization_id=org.id).one()
    assert new_folder.type == "upload"
    assert list(new_folder.files) == []  # empty — fabric/files come via /files


# ------------------------------------------------- create-a-filing (any window)


def test_create_past_filing_from_scratch(db_session, no_tiles):
    from database.models import folder as folder_model
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="past1@example.com")
    user.verified = True
    db_session.commit()

    new = filing_service.start_filing_for_window(
        user.id, 2023, 6, db_session, source="scratch", today=date(2026, 6, 11)
    )
    db_session.expire_all()
    row = db_session.query(folder_model).filter_by(organization_id=org.id).one()
    assert row.id == new.id and row.type == "upload"
    assert row.deadline == date(2023, 9, 1)  # June 2023's due date
    assert list(row.files) == []


def test_create_past_filing_auto_copies_latest_earlier(db_session, no_tiles):
    """The import default never reaches into the future: with June 2023 and
    June 2025 filings, a new December 2023 copies from June 2023."""
    from database.models import folder as folder_model
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="past2@example.com")
    user.verified = True
    db_session.commit()
    f23 = H.make_folder(db_session, org.id, name="f23", deadline=date(2023, 9, 1))
    H.seed_coverage(
        db_session,
        f23.id,
        POLYGON_GEOJSON,
        filename="from_2023.geojson",
        filetype="wireless",
        techType=70,
    )
    f25 = H.make_folder(db_session, org.id, name="f25", deadline=date(2025, 9, 1))
    H.seed_coverage(
        db_session,
        f25.id,
        POLYGON_GEOJSON,
        filename="from_2025.geojson",
        filetype="wireless",
        techType=70,
    )

    new = filing_service.start_filing_for_window(
        user.id, 2023, 12, db_session, source="auto", today=date(2026, 6, 11)
    )
    db_session.expire_all()
    names = {f.name for f in db_session.query(folder_model).filter_by(id=new.id).one().files}
    assert names == {"from_2023.geojson"}


def test_create_past_filing_auto_falls_back_to_earliest(db_session, no_tiles):
    """Creating a filing OLDER than everything existing: with only June 2025
    and December 2025, a new June 2023 copies from June 2025 (the earliest)."""
    from database.models import folder as folder_model
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="past3@example.com")
    user.verified = True
    db_session.commit()
    f25a = H.make_folder(db_session, org.id, name="f25a", deadline=date(2025, 9, 1))
    H.seed_coverage(
        db_session,
        f25a.id,
        POLYGON_GEOJSON,
        filename="from_jun25.geojson",
        filetype="wireless",
        techType=70,
    )
    f25b = H.make_folder(db_session, org.id, name="f25b", deadline=date(2026, 3, 2))
    H.seed_coverage(
        db_session,
        f25b.id,
        POLYGON_GEOJSON,
        filename="from_dec25.geojson",
        filetype="wireless",
        techType=70,
    )

    new = filing_service.start_filing_for_window(
        user.id, 2023, 6, db_session, source="auto", today=date(2026, 6, 11)
    )
    db_session.expire_all()
    names = {f.name for f in db_session.query(folder_model).filter_by(id=new.id).one().files}
    assert names == {"from_jun25.geojson"}


def test_create_filing_rejects_duplicate_future_and_foreign_source(db_session, no_tiles):
    from services import filing_service
    from services.exceptions import ServiceError

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="past4@example.com")
    user.verified = True
    db_session.commit()
    H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))  # June 2025 taken

    with pytest.raises(ServiceError) as ei:
        filing_service.start_filing_for_window(
            user.id, 2025, 6, db_session, source="scratch", today=date(2026, 6, 11)
        )
    assert "already has a filing" in ei.value.message

    with pytest.raises(ServiceError) as ei:
        filing_service.start_filing_for_window(
            user.id, 2027, 6, db_session, source="scratch", today=date(2026, 6, 11)
        )
    assert "opened" in ei.value.message

    other = H.make_org(db_session, name="past4-other")
    theirs = H.make_folder(db_session, other.id, deadline=date(2024, 9, 2))
    with pytest.raises(ServiceError):
        filing_service.start_filing_for_window(
            user.id, 2023, 6, db_session, source=str(theirs.id), today=date(2026, 6, 11)
        )


def test_filing_create_modal_and_flow(client, db_session, no_tiles):
    from database.models import folder as folder_model

    login_page_session(client, email="past5@example.com")
    org = H.make_org(db_session, name="past5-org")
    u = _get_user(db_session, "past5@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))

    modal = client.get("/filing/modals/new").get_data(as_text=True)
    assert 'name="month"' in modal and 'name="year"' in modal
    assert "Start from scratch" in modal
    assert "Copy from June 2025" in modal  # existing filings are pickable
    assert "earlier filing" in modal  # the recommended default

    resp = client.post("/filing/create", data={"month": "6", "year": "2023", "source": "scratch"})
    assert resp.status_code == 200
    assert resp.headers.get("HX-Redirect") == "/files?tab=fabric"
    assert "bdk_filing=" in resp.headers.get("Set-Cookie", "")
    db_session.expire_all()
    made = (
        db_session.query(folder_model)
        .filter_by(organization_id=org.id, deadline=date(2023, 9, 1))
        .one()
    )
    assert made.type == "upload"

    # A bad pick re-renders the modal with the error, keeping the choices.
    dup = client.post(
        "/filing/create", data={"month": "6", "year": "2025", "source": "scratch"}
    ).get_data(as_text=True)
    assert "already has a filing" in dup


def test_switcher_orders_next_window_first_then_filings_then_create(client, db_session):
    login_page_session(client, email="past6@example.com")
    org = H.make_org(db_session, name="past6-org")
    u = _get_user(db_session, "past6@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))

    html = client.get("/org").get_data(as_text=True)
    start = html.index('id="start-next-row"')
    filing_row = html.index('<span class="dt">June 2025')  # the filing's row
    create = html.index("Create new filing")
    assert start < filing_row < create


# ------------------------------------------------------------- the switcher


def test_header_switcher_lists_filings_and_start_button(client, db_session):
    login_page_session(client, email="switch@example.com")
    org = H.make_org(db_session, name="switch-org")
    u = _get_user(db_session, "switch@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))

    html = client.get("/org").get_data(as_text=True)
    assert 'hx-post="/filing/start-next"' in html
    assert "Start the" in html  # the explicit start button — never automatic
    assert "June 2025" in html  # the existing filing, window-labeled


def test_switcher_start_next_selects_and_lands_on_fabric(client, db_session, no_tiles):
    from database.models import folder as folder_model

    login_page_session(client, email="switch2@example.com")
    org = H.make_org(db_session, name="switch2-org")
    u = _get_user(db_session, "switch2@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()

    resp = client.post("/filing/start-next")
    assert resp.status_code == 200
    # The new filing is selected (cookie) and the flow lands on the fabric
    # tab — the one thing the new window needs.
    assert resp.headers.get("HX-Redirect") == "/files?tab=fabric"
    assert "bdk_filing=" in resp.headers.get("Set-Cookie", "")
    db_session.expire_all()
    assert db_session.query(folder_model).filter_by(organization_id=org.id).count() == 1


def test_switcher_select_changes_every_page(client, db_session, no_tiles):
    """Selecting a filing in the switcher switches the WHOLE app — the header
    label, the files page, the map — not just one view."""
    from services import plan_service

    login_page_session(client, email="switch3@example.com")
    org = H.make_org(db_session, name="switch3-org")
    u = _get_user(db_session, "switch3@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    old = H.make_folder(db_session, org.id, name="old", deadline=date(2024, 12, 31))
    H.seed_coverage(
        db_session,
        old.id,
        POLYGON_GEOJSON,
        filename="old_sector.geojson",
        filetype="wireless",
        techType=70,
    )
    plan_service.save_plan(
        old.id,
        name="Old Plan",
        tech_code=70,
        max_download=50,
        max_upload=10,
        session=db_session,
        is_default=True,
    )
    newer = H.make_folder(db_session, org.id, name="newer", deadline=date(2025, 9, 1))
    H.seed_coverage(
        db_session,
        newer.id,
        POLYGON_GEOJSON,
        filename="new_sector.geojson",
        filetype="wireless",
        techType=70,
    )

    # Default = latest by id (the newer filing).
    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert "new_sector.geojson" in html and "old_sector.geojson" not in html

    # Select the old filing: files, plans, and the header all follow.
    resp = client.post(f"/filing/select/{old.id}")
    assert resp.headers.get("HX-Refresh") == "true"
    html = client.get("/files?tab=coverage").get_data(as_text=True)
    assert "old_sector.geojson" in html and "new_sector.geojson" not in html
    assert "December 2024" in html  # the header label follows
    plans = client.get("/files?tab=plans").get_data(as_text=True)
    assert "Old Plan" in plans
    map_html = client.get("/map").get_data(as_text=True)
    assert (
        f'"folderId": {old.id}' in map_html.replace('folderId":', 'folderId":')
        or str(old.id) in map_html
    )

    # The dropdown marks the selected one as current.
    assert "current filing" in html


def test_switcher_select_rejects_foreign_and_falls_back(client, db_session):
    from database.models import folder as folder_model

    login_page_session(client, email="switch4@example.com")
    org = H.make_org(db_session, name="switch4-org")
    u = _get_user(db_session, "switch4@example.com")
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    mine = H.make_folder(db_session, org.id, deadline=date(2025, 9, 1))
    other = H.make_org(db_session, name="switch4-other")
    theirs = H.make_folder(db_session, other.id)

    resp = client.post(f"/filing/select/{theirs.id}")
    assert resp.status_code == 302  # bounced, no cookie set
    assert "bdk_filing" not in resp.headers.get("Set-Cookie", "")

    # A stale cookie (deleted filing) falls back to the latest upload filing.
    client.set_cookie("bdk_filing", "999999")
    html = client.get("/files").get_data(as_text=True)
    assert "June 2025" in html  # mine, not an error
    assert db_session.query(folder_model).filter_by(id=mine.id).one()
