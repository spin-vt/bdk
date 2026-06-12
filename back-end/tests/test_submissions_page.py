"""The submissions page (/submissions) + the debt selector + generate-as-a-job.

Pins:
  - the debt selector (fabric / default-plan-per-tech-in-use / Provider ID)
    and the header badge it feeds ("N tasks to finish" / "Ready to submit");
  - the generate sheet as the app's ONLY hard gate: generating refuses while
    debts stand, and nothing else in the app blocks;
  - generate runs as a job (operation Export → the pill says "Generating
    submission…"); the snapshot freezes the filing + CSV, downloads are
    byte-stable, and generating twice is normal;
  - mark-as-filed / reopen round-trips, with the filed chip in the header;
  - the language is "generate a submission" — never "export CSV".
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session, make_active_fabric_csv

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

FABRIC_ROWS = [
    (1001, "1 MAIN ST", "TRUE", 37.28, -79.95, "51161", "VA"),
    (1002, "2 ELM AVE", "TRUE", 37.50, -79.95, "51161", "VA"),
]

POLYGON_GEOJSON = b"""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},
"geometry":{"type":"Polygon","coordinates":[[[-80.01,37.27],[-79.90,37.27],[-79.90,37.31],
[-80.01,37.31],[-80.01,37.27]]]}}]}"""


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


def _login_with_filing(client, db_session, email, provider_id=330054):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=f"org-{email}", provider_id=provider_id)
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.verified = True
    db_session.commit()
    folder = H.make_folder(db_session, org.id)
    return org, folder


def _make_ready(db_session, folder):
    """Fabric + computed coverage + a default plan: zero debts."""
    from services import plan_service

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
    plan_service.save_plan(
        folder.id,
        name="AirLink",
        tech_code=70,
        max_download=100,
        max_upload=20,
        session=db_session,
        is_default=True,
    )
    return cov


# ------------------------------------------------------------- debt selector


def test_submission_debts_lists_everything_missing(db_session):
    from services import filing_service

    org = H.make_org(db_session, provider_id=None)
    user = H.make_user(db_session, org_id=org.id, email="debts@example.com")
    folder = H.make_folder(db_session, org.id)
    H.seed_coverage(
        db_session,
        folder.id,
        POLYGON_GEOJSON,
        filename="sector.geojson",
        filetype="wireless",
        techType=70,
    )

    ids = {d["id"] for d in filing_service.submission_debts(user.id, folder.id, db_session)}
    assert ids == {"fabric", "plan:70", "provider_id"}


def test_submission_debts_empty_when_ready(db_session):
    from services import filing_service

    org = H.make_org(db_session)
    user = H.make_user(db_session, org_id=org.id, email="ready@example.com")
    folder = H.make_folder(db_session, org.id)
    _make_ready(db_session, folder)
    assert filing_service.submission_debts(user.id, folder.id, db_session) == []


def test_header_badge_counts_and_clears(client, db_session):
    org, folder = _login_with_filing(client, db_session, "badge@example.com", provider_id=None)
    H.seed_coverage(
        db_session,
        folder.id,
        POLYGON_GEOJSON,
        filename="sector.geojson",
        filetype="wireless",
        techType=70,
    )
    html = client.get("/org").get_data(as_text=True)
    assert "3 tasks to finish" in html
    assert "Generate submission…" in html

    org.provider_id = 330054
    db_session.commit()
    _make_ready(db_session, folder)
    html = client.get("/org").get_data(as_text=True)
    assert "Ready to submit" in html


# ------------------------------------------------------------- generate sheet


def test_generate_sheet_shows_gates_with_fixes(client, db_session):
    org, folder = _login_with_filing(client, db_session, "sheet@example.com", provider_id=None)
    html = client.get("/submissions/sheet").get_data(as_text=True)
    assert "Generate submission" in html
    assert "No fabric loaded" in html and "BDC Provider ID missing" in html
    assert 'href="/files?tab=fabric"' in html and 'href="/org"' in html
    assert "disabled" in html  # Generate is not clickable

    # The page itself never says "export CSV".
    page = client.get("/submissions").get_data(as_text=True)
    assert "export CSV" not in page
    assert "Generate submission" in page


def test_generate_refused_while_debts_stand(client, db_session):
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "refuse@example.com", provider_id=None)
    resp = client.post("/submissions/generate")
    assert resp.status_code == 200
    assert "BDC Provider ID missing" in resp.get_data(as_text=True)  # the sheet again
    assert db_session.query(celerytaskinfo).count() == 0  # nothing dispatched


def test_generate_runs_as_a_job_and_twice_is_normal(client, db_session):
    from database.models import celerytaskinfo
    from database.models import file as file_model
    from database.models import folder as folder_model

    org, folder = _login_with_filing(client, db_session, "gen@example.com")
    _make_ready(db_session, folder)

    resp = client.post("/submissions/generate")
    assert resp.status_code == 200
    db_session.expire_all()
    info = db_session.query(celerytaskinfo).filter_by(operation_type="Export").one()
    assert info.organization_id == org.id

    snaps = db_session.query(folder_model).filter_by(type="export").all()
    assert len(snaps) == 1
    csv_file = db_session.query(file_model).filter_by(folder_id=snaps[0].id, type="export").one()
    assert b"location_id" in csv_file.data and b"1001" in csv_file.data
    # The snapshot carries the fabric vintage columns (copied with the folder).
    snap_fabric = db_session.query(file_model).filter_by(folder_id=snaps[0].id, type="fabric").one()
    assert snap_fabric is not None

    # Generating again is normal: a second frozen snapshot.
    client.post("/submissions/generate")
    db_session.expire_all()
    assert db_session.query(folder_model).filter_by(type="export").count() == 2


def test_submissions_page_lists_snapshots_with_download(client, db_session):
    org, folder = _login_with_filing(client, db_session, "list@example.com")
    _make_ready(db_session, folder)
    client.post("/submissions/generate")

    html = client.get("/submissions").get_data(as_text=True)
    assert "Download CSV" in html
    assert "/api/downloadexport/" in html

    from database.models import file as file_model

    db_session.expire_all()
    csv_file = db_session.query(file_model).filter_by(type="export").one()
    first = client.get(f"/api/downloadexport/{csv_file.id}").data
    assert first == csv_file.data  # byte-stable: stored bytes, not a rebuild


# ------------------------------------------------- wrong fabric version


def _wrong_vintage(db_session, folder):
    """Stamp the filing's active fabric with a vintage its window doesn't
    expect (deadline 2024-05-14 → December 2023 window → v4; this is v8)."""
    from datetime import date as _date

    from database.models import file as file_model

    fab = (
        db_session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type == "fabric")
        .one()
    )
    fab.fabric_data_as_of = _date(2025, 12, 31)
    db_session.commit()


def test_wrong_fabric_version_warns_loudly_but_allows(client, db_session):
    """A known-wrong fabric vintage is allowed but worn loudly: a red warning
    + click-through confirm on the generate sheet (NOT a debt — generating
    still works), a red version chip on the snapshot row, and the header
    badge turns from 'Ready to submit' into a warning."""
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "vintage@example.com")
    _make_ready(db_session, folder)
    _wrong_vintage(db_session, folder)

    # The generate sheet: red warning row + must-click-through confirm.
    html = client.get("/submissions/sheet").get_data(as_text=True)
    assert "wrong version" in html.lower() or "Wrong fabric version" in html
    assert "hx-confirm" in html
    assert "expects v4" in html and "v8" in html
    assert "disabled" not in html  # still allowed — a warning, not a gate

    # Generating goes through.
    client.post("/submissions/generate")
    db_session.expire_all()
    assert db_session.query(celerytaskinfo).filter_by(operation_type="Export").count() == 1

    # The snapshot row wears a red version chip.
    html = client.get("/submissions/list").get_data(as_text=True)
    assert "v8 · wrong version" in html

    # The header badge warns instead of saying all clear.
    html = client.get("/org").get_data(as_text=True)
    assert "Ready to submit" not in html
    assert "wrong fabric" in html.lower()
    assert "debt-on" in html


def test_matching_fabric_version_stays_quiet(client, db_session):
    """The matching-vintage filing keeps the calm chips and badge."""
    from datetime import date as _date

    from database.models import file as file_model

    org, folder = _login_with_filing(client, db_session, "vintageok@example.com")
    _make_ready(db_session, folder)
    fab = (
        db_session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type == "fabric")
        .one()
    )
    fab.fabric_data_as_of = _date(2023, 12, 31)  # v4 — exactly what the window expects
    db_session.commit()

    html = client.get("/submissions/sheet").get_data(as_text=True)
    assert "hx-confirm" not in html
    client.post("/submissions/generate")
    html = client.get("/submissions/list").get_data(as_text=True)
    assert "wrong version" not in html and "v4" in html
    html = client.get("/org").get_data(as_text=True)
    assert "Ready to submit" in html


# ------------------------------------------------- generate job lifecycle


def test_generate_job_lands_success_not_stuck_pending(client, db_session):
    """REGRESSION: the task-info row must exist BEFORE the job is dispatched.
    task_postrun updates the row by task_id, and a fast job (eager here,
    near-instant in prod) finished before the route inserted the row — postrun
    found nothing, the row stayed PENDING, and the page said "Generating"
    forever even with the CSV sitting in the list."""
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "race@example.com")
    _make_ready(db_session, folder)

    client.post("/submissions/generate")
    db_session.expire_all()
    info = db_session.query(celerytaskinfo).filter_by(operation_type="Export").one()
    assert info.status == "SUCCESS"
    html = client.get("/submissions/list").get_data(as_text=True)
    assert "Generating" not in html


def test_snapshot_is_built_inside_the_generate_job(client, db_session, monkeypatch):
    """The generate job itself freezes the snapshot, so the job reporting
    finished means the CSV is downloadable. (It used to hand off to a nested
    fire-and-forget copy task that could land after — or never.)"""
    from controllers.celery_controller import celery_tasks
    from database.models import folder as folder_model

    nested = []
    monkeypatch.setattr(
        celery_tasks.async_folder_copy_for_export,
        "apply_async",
        lambda *a, **k: nested.append(a),
    )
    org, folder = _login_with_filing(client, db_session, "inline@example.com")
    _make_ready(db_session, folder)

    client.post("/submissions/generate")
    db_session.expire_all()
    assert db_session.query(folder_model).filter_by(type="export").count() == 1
    assert nested == []  # no detached copy task — the snapshot is the job


def test_completion_opens_submission_ready_modal(client, db_session):
    """When the generate job lands, the 'Submission ready' modal opens asking
    to mark the filing as filed (spec rule 13). Eager Celery makes the job
    finish within the POST, so the modal rides back on that response."""
    org, folder = _login_with_filing(client, db_session, "modal@example.com")
    _make_ready(db_session, folder)

    html = client.post("/submissions/generate").get_data(as_text=True)
    assert "Submission ready" in html
    assert "Mark as filed" in html and "Not yet" in html
    assert "hx-swap-oob" in html  # delivered out-of-band into #modal-slot

    # A plain list render never re-opens it.
    html = client.get("/submissions/list").get_data(as_text=True)
    assert "Submission ready" not in html


def test_watch_poll_opens_modal_only_when_job_lands(client, db_session):
    """The prod sequence: the job is still running at POST time, the list
    polls with watch=1, and the modal opens on the poll that sees it land."""
    from controllers.database_controller import celerytaskinfo_ops
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "watch@example.com")
    _make_ready(db_session, folder)
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id="watch-test-task",
        status="PENDING",
        operation_type="Export",
        operation_detail="Generate a submission",
        user_email="watch@example.com",
        organization_id=org.id,
        folder_deadline=folder.deadline,
        session=db_session,
    )

    html = client.get("/submissions/list?watch=1").get_data(as_text=True)
    assert "Generating" in html and "Submission ready" not in html
    assert "/submissions/list?watch=1" in html  # keeps polling

    row = db_session.query(celerytaskinfo).filter_by(task_id="watch-test-task").one()
    row.status = "SUCCESS"
    db_session.commit()

    html = client.get("/submissions/list?watch=1").get_data(as_text=True)
    assert "Submission ready" in html

    # Without watch (a fresh page load later) the landed job stays quiet.
    html = client.get("/submissions/list").get_data(as_text=True)
    assert "Submission ready" not in html


def test_watch_poll_reports_a_failed_generate(client, db_session):
    """A generate that dies must say so instead of spinning forever."""
    from controllers.database_controller import celerytaskinfo_ops
    from database.models import celerytaskinfo

    org, folder = _login_with_filing(client, db_session, "fail@example.com")
    _make_ready(db_session, folder)
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id="fail-test-task",
        status="PENDING",
        operation_type="Export",
        operation_detail="Generate a submission",
        user_email="fail@example.com",
        organization_id=org.id,
        folder_deadline=folder.deadline,
        session=db_session,
    )
    row = db_session.query(celerytaskinfo).filter_by(task_id="fail-test-task").one()
    row.status = "FAILURE"
    db_session.commit()

    html = client.get("/submissions/list?watch=1").get_data(as_text=True)
    assert "failed" in html.lower()
    assert "Submission ready" not in html


# ------------------------------------------------------------- filed state


def test_mark_filed_and_reopen_roundtrip(client, db_session):
    org, folder = _login_with_filing(client, db_session, "filed@example.com")
    _make_ready(db_session, folder)
    client.post("/submissions/generate")

    resp = client.post("/submissions/filed")
    assert "Reopen" in resp.get_data(as_text=True)
    db_session.expire_all()
    assert folder.status == "filed"

    # The header now wears the filed chip instead of the debt badge.
    html = client.get("/org").get_data(as_text=True)
    assert "filed ✓" in html and "Ready to submit" not in html

    resp = client.post("/submissions/reopen")
    db_session.expire_all()
    assert folder.status == "open"
    assert "Generate submission…" in resp.get_data(as_text=True)


# ------------------------------------------------------------- CSRF


def test_submissions_posts_require_csrf(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as plain:
        login_page_session(plain, email="csrf-sub@example.com")
        org = H.make_org(db_session, name="csrf-sub-org")
        u = _get_user(db_session, "csrf-sub@example.com")
        u.organization_id = org.id
        db_session.commit()
        folder = H.make_folder(db_session, org.id)

        resp = plain.post("/submissions/filed")
        assert resp.status_code == 302
        db_session.expire_all()
        assert folder.status != "filed"


def test_empty_filing_is_not_ready_to_submit(client, db_session):
    """A filing with a fabric but no coverage must not read "Ready to submit"
    — an empty CSV is technically possible but only confusing."""
    from services import filing_service

    org, folder = _login_with_filing(client, db_session, "empty@example.com")
    H.seed_fabric(db_session, folder.id, make_active_fabric_csv(FABRIC_ROWS))

    debts = filing_service.submission_debts(
        _get_user(db_session, "empty@example.com").id, folder.id, db_session
    )
    assert any(d["id"] == "coverage" for d in debts)

    html = client.get("/org").get_data(as_text=True)
    assert "Ready to submit" not in html
    assert "No network coverage yet" in html


def test_snapshots_never_leak_across_filings(client, db_session):
    """HARD CONSTRAINT: a filing's submissions list shows only ITS snapshots.
    Snapshots record the filing they were generated from (folder lineage)."""
    from database.models import folder as folder_model

    org, folder_a = _login_with_filing(client, db_session, "leak@example.com")
    _make_ready(db_session, folder_a)
    client.post("/submissions/generate")  # snapshot of filing A

    # A second filing in another window, with its own snapshot.
    from datetime import date as _date

    folder_b = H.make_folder(db_session, org.id, name="B", deadline=_date(2099, 9, 1))
    _make_ready(db_session, folder_b)
    client.set_cookie("bdk_filing", str(folder_b.id))
    client.post("/submissions/generate")  # snapshot of filing B
    db_session.expire_all()
    assert db_session.query(folder_model).filter_by(type="export").count() == 2

    # Filing B's list shows exactly its own snapshot...
    html = client.get("/submissions").get_data(as_text=True)
    assert html.count("Download CSV") == 1

    # ...and so does filing A's.
    client.set_cookie("bdk_filing", str(folder_a.id))
    html = client.get("/submissions").get_data(as_text=True)
    assert html.count("Download CSV") == 1

    # The lineage is explicit on the model, not inferred.
    snaps = db_session.query(folder_model).filter_by(type="export").all()
    assert {s.source_folder_id for s in snaps} == {folder_a.id, folder_b.id}
