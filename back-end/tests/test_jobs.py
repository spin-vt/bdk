"""Jobs & SSE v2 — the async backbone behind the header job pill/tray.

Pins:
  - the plain-language job catalog: every operation a worker can run maps to
    label/sub copy a provider understands (no operation codes, no tracebacks);
  - the org-scoped jobs snapshot that drives the pill ("Up to date" /
    "Map updating…" / "Generating submission…") and the tray (active jobs,
    recent done, failures in plain words with a way out — never raw results);
  - stuck-task detection: stale PENDING/STARTED/RETRY rows are marked FAILURE
    (a mid-chain crash leaves the chain's final task PENDING forever — this is
    the only thing that ever resolves those);
  - the SSE stream at /api/jobs/events (shared `token` session, org-scoped,
    text/event-stream, pill+tray fragments, nginx buffering disabled).
"""

from datetime import datetime, timedelta

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def job_service():
    from services import job_service

    return job_service


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def make_taskinfo(
    session,
    org_id,
    task_id="t-1",
    status="PENDING",
    operation_type="Upload",
    operation_detail="Create a new filing",
    files_changed=None,
    result=None,
    start_time=None,
):
    from database.models import celerytaskinfo

    row = celerytaskinfo(
        task_id=task_id,
        status=status,
        operation_type=operation_type,
        operation_detail=operation_detail,
        start_time=start_time or datetime.now(),
        user_email="dev@example.com",
        organization_id=org_id,
        folder_deadline=datetime(2025, 9, 1).date(),
        files_changed=files_changed,
        result=result,
    )
    session.add(row)
    session.commit()
    return row


# ---------------------------------------------------------------- catalog


def test_catalog_covers_every_operation_in_plain_words(job_service):
    """Every (operation_type, operation_detail) the codebase actually writes
    maps to plain-language copy — labels a provider understands."""
    cases = [
        # (type, detail, files_changed) -> expected label
        ("Upload", "Create a new filing", "a.kml, b.kml", "Reading 2 network files"),
        ("Upload", "Add more files to a filing", "a.kml", "Reading 1 network file"),
        (
            "Upload",
            "Create a new Filing by importing from filing with deadline 2025-09",
            None,
            "Copying your last filing",
        ),
        ("Fabric", "Replace the fabric", "fabric.csv", "Replacing the fabric"),
        ("Fabric", "Add the fabric", "fabric.csv", "Processing the fabric"),
        ("Edit", "Edit a filing", None, "Finalizing your edit"),
        ("Update", "Regenerate Map", None, "Rebuilding map tiles"),
        ("Update", "Update filename or filetype in a filing", None, "Updating file details"),
        ("Delete", "Delete a filing", None, "Deleting a filing"),
        ("Delete", "Delete files in a filing", None, "Removing files"),
        ("Delete", "Delete a filing export snapshot", None, "Deleting a submission snapshot"),
        ("Export", None, None, "Generating submission"),
    ]
    for op_type, detail, files, expected_label in cases:
        desc = job_service.describe_job(op_type, detail, files)
        assert desc["label"] == expected_label, (op_type, detail)
        assert "sub" in desc


def test_catalog_unknown_operation_falls_back_gracefully(job_service):
    desc = job_service.describe_job("Frobnicate", "Frobnicate the widget", None)
    assert desc["label"] == "Working in the background"
    assert desc["sub"] == "Frobnicate the widget"


def test_failure_text_is_plain_with_a_way_out(job_service):
    """Failure copy never exposes internals and always says what to do next."""
    for op_type in ("Upload", "Fabric", "Edit", "Update", "Delete", "Export", "Whatever"):
        text = job_service.failure_text(op_type)
        assert "try" in text.lower(), op_type
        assert "Traceback" not in text and "Exception" not in text


# ---------------------------------------------------------------- snapshot


def test_snapshot_idle(job_service, db_session):
    org = H.make_org(db_session)
    snap = job_service.org_jobs_snapshot(org.id, db_session)
    assert snap["busy"] is False
    assert snap["pill"] == "Up to date"
    assert snap["active"] == []
    assert snap["recent"] == []


def test_snapshot_no_org_is_idle(job_service, db_session):
    snap = job_service.org_jobs_snapshot(None, db_session)
    assert snap["busy"] is False
    assert snap["pill"] == "Up to date"


def test_snapshot_busy_and_org_scoped(job_service, db_session):
    s = db_session
    org_a = H.make_org(s, name="OrgA")
    org_b = H.make_org(s, name="OrgB")
    make_taskinfo(s, org_a.id, task_id="t-a", files_changed="net.kml")

    snap_a = job_service.org_jobs_snapshot(org_a.id, s)
    assert snap_a["busy"] is True
    assert snap_a["pill"] == "Map updating…"
    assert snap_a["active"][0]["label"] == "Reading 1 network file"

    snap_b = job_service.org_jobs_snapshot(org_b.id, s)
    assert snap_b["busy"] is False
    assert snap_b["active"] == []


def test_snapshot_export_running_changes_pill(job_service, db_session):
    s = db_session
    org = H.make_org(s)
    make_taskinfo(s, org.id, task_id="t-up", operation_type="Upload")
    make_taskinfo(s, org.id, task_id="t-ex", operation_type="Export", operation_detail=None)
    snap = job_service.org_jobs_snapshot(org.id, s)
    assert snap["pill"] == "Generating submission…"


def test_snapshot_failures_in_plain_words_never_raw_results(job_service, db_session):
    """A failed job's tray row shows catalog copy + a way out — never the
    stored result string (which is str(retval): tracebacks, repr noise)."""
    s = db_session
    org = H.make_org(s)
    make_taskinfo(
        s,
        org.id,
        task_id="t-f",
        status="FAILURE",
        operation_type="Upload",
        result="Traceback (most recent call last): ValueError('secret-path/x.kml')",
    )
    snap = job_service.org_jobs_snapshot(org.id, s)
    assert snap["busy"] is False
    row = snap["recent"][0]
    assert row["ok"] is False
    assert "Traceback" not in row["note"] and "secret-path" not in row["note"]
    assert row["note"] == job_service.failure_text("Upload")


def test_snapshot_recent_is_limited_and_newest_first(job_service, db_session):
    s = db_session
    org = H.make_org(s)
    base = datetime.now()
    for i in range(7):
        make_taskinfo(
            s,
            org.id,
            task_id=f"t-{i}",
            status="SUCCESS",
            start_time=base + timedelta(minutes=i),
            operation_type="Edit",
            operation_detail="Edit a filing",
        )
    snap = job_service.org_jobs_snapshot(org.id, s)
    assert len(snap["recent"]) == 5
    assert all(r["ok"] for r in snap["recent"])


def test_snapshot_active_oldest_first(job_service, db_session):
    s = db_session
    org = H.make_org(s)
    now = datetime.now()
    make_taskinfo(s, org.id, task_id="t-2", operation_type="Edit", start_time=now)
    make_taskinfo(
        s,
        org.id,
        task_id="t-1",
        operation_type="Upload",
        files_changed="a.kml",
        start_time=now - timedelta(minutes=5),
    )
    snap = job_service.org_jobs_snapshot(org.id, s)
    assert [a["label"] for a in snap["active"]] == [
        "Reading 1 network file",
        "Finalizing your edit",
    ]


# ---------------------------------------------------------------- stuck tasks


def test_sweep_marks_stale_active_as_failure(job_service, db_session):
    s = db_session
    org = H.make_org(s)
    stale = make_taskinfo(
        s, org.id, task_id="t-stale", start_time=datetime.now() - timedelta(hours=3)
    )
    fresh = make_taskinfo(s, org.id, task_id="t-fresh", start_time=datetime.now())
    done = make_taskinfo(
        s,
        org.id,
        task_id="t-done",
        status="SUCCESS",
        start_time=datetime.now() - timedelta(hours=30),
    )

    n = job_service.sweep_stuck_tasks(s, max_age_seconds=7200)
    assert n == 1
    s.expire_all()
    assert stale.status == "FAILURE"
    assert fresh.status == "PENDING"
    assert done.status == "SUCCESS"
    # The stored result is a plain sentence, not machine noise.
    assert "too long" in stale.result


def test_sweep_threshold_is_configurable(job_service, db_session):
    s = db_session
    org = H.make_org(s)
    row = make_taskinfo(s, org.id, task_id="t-x", start_time=datetime.now() - timedelta(seconds=90))
    assert job_service.sweep_stuck_tasks(s, max_age_seconds=3600) == 0
    assert job_service.sweep_stuck_tasks(s, max_age_seconds=60) == 1
    s.expire_all()
    assert row.status == "FAILURE"


def test_stuck_sweep_is_on_the_beat_schedule():
    """Celery Beat periodically runs the sweep (the worker runs with -B)."""
    from controllers.celery_controller.celery_config import celery

    entry = celery.conf.beat_schedule.get("sweep-stuck-tasks")
    assert entry is not None
    assert entry["task"].endswith("sweep_stuck_tasks")
    assert entry["schedule"] <= 600


# ---------------------------------------------------------------- SSE stream


def _attach_org(db_session, email):
    """Give a freshly-registered page-session user an organization."""
    from database.models import user as user_model

    org = H.make_org(db_session, name=f"org-{email}")
    u = db_session.query(user_model).filter(user_model.email == email).one()
    u.organization_id = org.id
    db_session.commit()
    return org


@pytest.fixture()
def fast_stream():
    from utils.flask_app import app

    app.config["JOBS_SSE_POLL_SECONDS"] = 0
    app.config["JOBS_SSE_MAX_TICKS"] = 2
    yield
    app.config.pop("JOBS_SSE_POLL_SECONDS", None)
    app.config.pop("JOBS_SSE_MAX_TICKS", None)


def test_jobs_events_requires_auth(client):
    resp = client.get("/api/jobs/events")
    assert resp.status_code == 401


def test_jobs_events_streams_pill_and_tray(client, db_session, fast_stream):
    login_page_session(client, email="sse@example.com")
    org = _attach_org(db_session, "sse@example.com")
    make_taskinfo(db_session, org.id, task_id="t-sse", files_changed="net.kml")

    resp = client.get("/api/jobs/events")
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    assert resp.headers["X-Accel-Buffering"] == "no"
    body = resp.get_data(as_text=True)
    assert "event: pill" in body
    assert "event: tray" in body
    assert "Map updating…" in body
    assert "Reading 1 network file" in body


def test_jobs_events_idle_without_org(client, fast_stream):
    """A user with no organization gets a quiet idle stream, not an error."""
    login_page_session(client, email="noorg@example.com")
    resp = client.get("/api/jobs/events")
    assert resp.status_code == 200
    assert "Up to date" in resp.get_data(as_text=True)


def test_jobs_events_is_org_scoped(client, db_session, fast_stream):
    """Another org's running job must not leak into my stream."""
    s = db_session
    other_org = H.make_org(s, name="other")
    make_taskinfo(s, other_org.id, task_id="t-other", files_changed="theirs.kml")
    login_page_session(client, email="mine@example.com")
    _attach_org(s, "mine@example.com")

    body = client.get("/api/jobs/events").get_data(as_text=True)
    assert "theirs" not in body
    assert "Up to date" in body and "Map up to date" not in body


# ---------------------------------------------------------------- shell wiring


def test_app_pages_carry_live_job_pill(client, db_session):
    """The shell connects the pill/tray to the SSE stream and server-renders
    the initial state (no flash of wrong state before the stream connects).
    The stream MUST be gated on tab visibility: every open EventSource holds
    one of the browser's ~6 per-host connections, so unconditional streams in
    a few open tabs hang every request to the app."""
    login_page_session(client, email="shell@example.com")
    org = _attach_org(db_session, "shell@example.com")
    make_taskinfo(db_session, org.id, task_id="t-shell", files_changed="net.kml")

    resp = client.get("/org")
    html = resp.get_data(as_text=True)
    assert "EventSource('/api/jobs/events')" in html
    assert 'id="job-pill"' in html and 'id="job-tray"' in html
    assert "visibilitychange" in html  # hidden tabs must release their stream
    assert "Map updating…" in html
    assert "Reading 1 network file" in html


def test_sweep_uses_tighter_threshold_for_generate_jobs(job_service, db_session):
    """A generate (Export) job normally finishes in minutes — a stranded one
    must be swept long before the general 2-hour threshold."""
    s = db_session
    org = H.make_org(s)
    gen = make_taskinfo(
        s,
        org.id,
        task_id="t-gen",
        operation_type="Export",
        start_time=datetime.now() - timedelta(minutes=20),
    )
    slow = make_taskinfo(
        s,
        org.id,
        task_id="t-slow",
        operation_type="Upload",
        start_time=datetime.now() - timedelta(minutes=20),
    )
    assert job_service.sweep_stuck_tasks(s, max_age_seconds=7200) == 1
    s.expire_all()
    assert gen.status == "FAILURE"  # 20 min > the Export threshold
    assert slow.status == "PENDING"  # a 20-minute upload is normal
