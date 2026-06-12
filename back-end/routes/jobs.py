"""The org-scoped jobs SSE stream feeding the header job pill and tray.

One stream per browser tab (`GET /api/jobs/events`, on the shared `token`
session): it polls the org's task-info rows and pushes re-rendered pill/tray
fragments only when something changed. The DB rows are the shared truth, so a
job started anywhere — the frozen SPA, a redesigned page, another user in the
org — narrates itself live on every connected page.

The stream closes itself after a few minutes (JOBS_SSE_MAX_TICKS); the
browser's EventSource (via the htmx SSE extension) reconnects transparently.
That bounds how long a worker thread can be held by one client.
"""

import time

from flask import Blueprint, Response, current_app, render_template
from flask_jwt_extended import get_jwt_identity, jwt_required

from controllers.database_controller import user_ops
from database.sessions import Session
from services import job_service

bp = Blueprint("jobs", __name__)


def _sse(event, html):
    """Format one SSE message; multi-line HTML needs every line data-prefixed."""
    lines = html.splitlines() or [""]
    return f"event: {event}\n" + "".join(f"data: {line}\n" for line in lines) + "\n"


def render_jobs_fragments(snapshot):
    """The pill and tray inner HTML — the same partials the page shell renders
    initially, so the SSE swap can never drift from first paint."""
    pill = render_template("app/_job_pill.html", jobs=snapshot)
    tray = render_template("app/_job_tray.html", jobs=snapshot)
    return pill, tray


@bp.route("/api/jobs/events", methods=["GET"])
@jwt_required()
def jobs_events():
    identity = get_jwt_identity()
    # A short-lived Session, not the request-scoped one: the scoped session is
    # only torn down when the RESPONSE finishes, which for this stream is
    # minutes away — it would pin one pooled connection per open viewer.
    session = Session()
    try:
        user_val = user_ops.get_user_with_id(userid=identity["id"], session=session)
        org_id = user_val.organization_id if user_val else None
    finally:
        session.close()

    app = current_app._get_current_object()
    poll = app.config.get("JOBS_SSE_POLL_SECONDS", 2.0)
    max_ticks = app.config.get("JOBS_SSE_MAX_TICKS", 150)

    def render_tick():
        # The generator outlives the request context. Each tick gets a fresh
        # short-lived Session (sees other processes' commits, never holds a
        # transaction open) and its own app context for the render — pushed
        # and popped within one generator step, never spanning a yield (a
        # context held across yields interleaves with other requests' stacks).
        session = Session()
        try:
            snapshot = job_service.org_jobs_snapshot(org_id, session)
        finally:
            session.close()
        with app.app_context():
            return render_jobs_fragments(snapshot)

    def stream():
        last = None
        for tick in range(max_ticks):
            pill, tray = render_tick()
            if (pill, tray) != last:
                yield _sse("pill", pill)
                yield _sse("tray", tray)
                last = (pill, tray)
            else:
                yield ": keepalive\n\n"
            if tick + 1 < max_ticks and poll:
                time.sleep(poll)

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["X-Accel-Buffering"] = "no"  # nginx: stream, don't buffer
    resp.headers["Cache-Control"] = "no-cache"
    return resp
