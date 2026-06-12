"""Org-scoped job narration — the data behind the header job pill and tray.

Reads the existing `celerytaskinfo` rows (one per dispatched chain, written by
the upload/edit/fabric/delete/retile flows and resolved by the worker's
task_postrun hook) and translates them into plain language a provider
understands. Nothing here talks to Celery directly: the DB row is the shared
truth, which is what lets a job started from the frozen SPA narrate itself on
a redesigned page (and vice versa).

Also owns stuck-task detection. A chain row is keyed by its FINAL task id, so
a crash in an earlier chain link leaves the row PENDING forever — the periodic
sweep (Celery Beat) is the only thing that ever resolves those.
"""

from datetime import datetime, timedelta

from database.models import celerytaskinfo
from utils.config import Config

# Statuses that mean "a worker still owes us a result".
ACTIVE_STATUSES = ("PENDING", "STARTED", "RETRY")

PILL_IDLE = "Up to date"
PILL_BUSY = "Map updating…"
PILL_EXPORT = "Generating submission…"

STUCK_RESULT = "Stopped after running too long without finishing"

# Plain-language catalog. Keyed by operation_type, refined by operation_detail
# substrings (the details are written by our own services, so matching on them
# is stable; anything unrecognized falls through to a safe generic line).
_FALLBACK = {"label": "Working in the background", "sub": ""}


def describe_job(operation_type, operation_detail=None, files_changed=None):
    """Plain words for one job: {label, sub}. Never echoes raw internals."""
    detail = operation_detail or ""

    if operation_type == "Upload":
        if "importing" in detail.lower():
            return {
                "label": "Copying your last filing",
                "sub": "carrying files, plans, and edits forward",
            }
        n = len([f for f in (files_changed or "").split(",") if f.strip()])
        label = (
            f"Reading {n} network file{'s' if n != 1 else ''}"
            if n
            else ("Reading your network files")
        )
        return {"label": label, "sub": "computing served locations · rebuilding map tiles"}

    if operation_type == "Fabric":
        if "replace" in detail.lower():
            return {
                "label": "Replacing the fabric",
                "sub": "recomputing served locations · re-applying your edits",
            }
        return {
            "label": "Processing the fabric",
            "sub": "matching your coverage against its locations",
        }

    if operation_type == "Edit":
        return {
            "label": "Finalizing your edit",
            "sub": "locations updated now · map tiles rebuild behind",
        }

    if operation_type == "Update":
        if "regenerate" in detail.lower():
            return {"label": "Rebuilding map tiles", "sub": "runs in the background"}
        return {"label": "Updating file details", "sub": "recomputing affected coverage"}

    if operation_type == "Delete":
        if "export" in detail.lower() or "snapshot" in detail.lower():
            return {"label": "Deleting a submission snapshot", "sub": ""}
        if "files" in detail.lower():
            return {"label": "Removing files", "sub": "recomputing served locations"}
        return {"label": "Deleting a filing", "sub": "removing its files and map"}

    if operation_type == "Export":
        return {"label": "Generating submission", "sub": "building the CSV"}

    return {"label": _FALLBACK["label"], "sub": detail or _FALLBACK["sub"]}


def failure_text(operation_type):
    """What a failed job means and what to do about it — plain words with a
    way out. Never the stored result string (str(retval): tracebacks etc.)."""
    return {
        "Upload": "We couldn't finish processing those files. Check the files and try the upload again.",
        "Fabric": "The fabric didn't finish processing. Try the upload again.",
        "Edit": "Your edit didn't finish saving. Open the map and try it again.",
        "Update": "The map didn't finish rebuilding. Try regenerating the map again.",
        "Delete": "The delete didn't finish. Try it again.",
        "Export": "The submission didn't generate. Try generating it again.",
    }.get(operation_type, "Something went wrong. Try the action again.")


def org_jobs_snapshot(org_id, session, recent_limit=5):
    """Everything the pill and tray need, for one organization:
    {busy, pill, active: [{label, sub}], recent: [{label, ok, note}]}."""
    if org_id is None:
        return {"busy": False, "pill": PILL_IDLE, "active": [], "recent": []}

    rows = (
        session.query(celerytaskinfo)
        .filter(celerytaskinfo.organization_id == org_id)
        .order_by(celerytaskinfo.start_time.desc())
        .limit(50)
        .all()
    )

    active = [r for r in reversed(rows) if r.status in ACTIVE_STATUSES]  # oldest first
    recent = [r for r in rows if r.status not in ACTIVE_STATUSES][:recent_limit]

    pill = PILL_IDLE
    if active:
        pill = PILL_EXPORT if any(r.operation_type == "Export" for r in active) else PILL_BUSY

    return {
        "busy": bool(active),
        "pill": pill,
        "active": [
            describe_job(r.operation_type, r.operation_detail, r.files_changed) for r in active
        ],
        "recent": [
            {
                "label": describe_job(r.operation_type, r.operation_detail, r.files_changed)[
                    "label"
                ],
                "ok": r.status == "SUCCESS",
                "note": None if r.status == "SUCCESS" else failure_text(r.operation_type),
            }
            for r in recent
        ],
    }


# Operations that normally finish in a minute or two get a much tighter stuck
# threshold than the general one — a user watching "Generating submission…"
# shouldn't wait two hours to learn the job died.
FAST_OPERATION_MAX_AGE = {"Export": 900}


def sweep_stuck_tasks(session, max_age_seconds=None, now=None):
    """Mark active rows older than their threshold as FAILURE. Returns how
    many were marked. Run periodically by Celery Beat (see celery_config)."""
    if max_age_seconds is None:
        max_age_seconds = Config.STUCK_TASK_MAX_AGE_SECONDS
    now = now or datetime.now()

    stuck = []
    for row in (
        session.query(celerytaskinfo)
        .filter(
            celerytaskinfo.status.in_(ACTIVE_STATUSES),
            celerytaskinfo.start_time.isnot(None),
        )
        .all()
    ):
        threshold = min(
            max_age_seconds, FAST_OPERATION_MAX_AGE.get(row.operation_type, max_age_seconds)
        )
        if row.start_time < now - timedelta(seconds=threshold):
            stuck.append(row)
    for row in stuck:
        row.status = "FAILURE"
        row.result = STUCK_RESULT
    if stuck:
        session.commit()
    return len(stuck)
