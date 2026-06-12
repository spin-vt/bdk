"""The submissions page (/submissions) — generate sheet, snapshots, filed state.

"Generate a submission", never "export CSV". The generate sheet is the app's
ONLY hard gate: it refuses while the debt selector reports anything missing.
A submission is a frozen snapshot (an export-type folder carrying a copy of
the filing plus the built CSV), so generating twice is normal and downloads
are byte-stable.
"""

import uuid

from flask import Blueprint, redirect, render_template, request

from controllers.celery_controller.celery_tasks import generate_submission
from controllers.database_controller import celerytaskinfo_ops, user_ops
from database.models import celerytaskinfo
from database.models import file as file_model
from database.sessions import get_session
from routes.app_pages import _inject_chrome, current_folder, page_session_required
from services import fabric_service, filing_service
from services.exceptions import ServiceError
from services.fabric_intake import version_for_data_as_of
from services.filing_windows import window_from_deadline
from services.job_service import ACTIVE_STATUSES

bp = Blueprint("submissions_page", __name__, template_folder="../templates")
bp.context_processor(_inject_chrome)


def _me_and_folder(identity, session):
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    return me, current_folder(me, session)


def _snapshot_rows(me, folder, session):
    """One row per submission snapshot OF THIS FILING (lineage-scoped — a
    filing's snapshots never leak into another's list). Snapshots created
    before lineage existed fall back to a same-deadline match."""
    from database.models import folder as folder_model

    snaps = (
        session.query(folder_model)
        .filter(
            folder_model.organization_id == me.organization_id,
            folder_model.type == "export",
        )
        .all()
    )
    rows = []
    for snap in snaps:
        if snap.source_folder_id is not None:
            if snap.source_folder_id != folder.id:
                continue
        elif snap.deadline != folder.deadline:
            continue
        csvs = (
            session.query(file_model)
            .filter(file_model.folder_id == snap.id, file_model.type == "export")
            .all()
        )
        fabric = (
            session.query(file_model)
            .filter(file_model.folder_id == snap.id, file_model.type == "fabric")
            .first()
        )
        for f in csvs:
            rows.append(
                {
                    "file_id": f.id,
                    "name": f.name,
                    "when": f.timestamp,
                    "fabric_version": version_for_data_as_of(fabric.fabric_data_as_of)
                    if fabric is not None and fabric.fabric_data_as_of
                    else None,
                }
            )
    rows.sort(key=lambda r: r["when"] or 0, reverse=True)
    return rows


def _generating(me, folder, session):
    """True while a generate job is still owed for THIS filing."""
    return (
        session.query(celerytaskinfo)
        .filter(
            celerytaskinfo.organization_id == me.organization_id,
            celerytaskinfo.operation_type == "Export",
            celerytaskinfo.folder_deadline == folder.deadline,
            celerytaskinfo.status.in_(ACTIVE_STATUSES),
        )
        .first()
        is not None
    )


def _last_export_status(me, folder, session):
    """Status of this filing's most recent generate job, or None."""
    row = (
        session.query(celerytaskinfo)
        .filter(
            celerytaskinfo.organization_id == me.organization_id,
            celerytaskinfo.operation_type == "Export",
            celerytaskinfo.folder_deadline == folder.deadline,
        )
        .order_by(celerytaskinfo.start_time.desc())
        .first()
    )
    return row.status if row else None


def _list_context(identity, session, watch=False):
    """Context for the list fragment. watch=True means the caller was watching
    a generate job (the poll, or the POST that dispatched it): if the job has
    landed, `landed` carries its status so the template can open the
    "Submission ready" modal (SUCCESS) or say it failed."""
    me, folder = _me_and_folder(identity, session)
    if me is None or me.organization_id is None or folder is None:
        return {"folder": None, "rows": [], "generating": False, "debts": [], "landed": None}
    generating = _generating(me, folder, session)
    landed = None
    if watch and not generating:
        landed = _last_export_status(me, folder, session)
    return {
        "folder": folder,
        "rows": _snapshot_rows(me, folder, session),
        "generating": generating,
        "debts": filing_service.submission_debts(me.id, folder.id, session),
        "landed": landed,
        "expected_fabric_version": window_from_deadline(folder.deadline).fabric_version,
    }


@bp.route("/submissions", strict_slashes=False)
@page_session_required
def submissions_page(identity):
    session = get_session()
    return render_template("app/submissions.html", **_list_context(identity, session))


@bp.route("/submissions/list")
@page_session_required
def submissions_list(identity):
    """The list fragment; polled by htmx (with ?watch=1) while a generate job
    is running, so completion can open the "Submission ready" modal."""
    session = get_session()
    watch = bool(request.args.get("watch"))
    return render_template(
        "app/_submissions_list.html", **_list_context(identity, session, watch=watch)
    )


@bp.route("/submissions/sheet")
@page_session_required
def generate_sheet(identity):
    """The generate sheet: every gate with ✓/! and a fix link; Generate is
    enabled only when all gates pass."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/submissions")
    debts = filing_service.submission_debts(me.id, folder.id, session)
    return render_template(
        "app/_generate_sheet.html",
        folder=folder,
        debts=debts,
        generating=_generating(me, folder, session),
        fabric_warning=fabric_service.fabric_vintage_warning(folder.id, session),
    )


@bp.route("/submissions/generate", methods=["POST"])
@page_session_required
def generate(identity):
    """Dispatch the generate job — refusing while any debt stands (this is the
    app's only hard gate; nothing else blocks)."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/submissions")
    debts = filing_service.submission_debts(me.id, folder.id, session)
    if debts:
        return render_template(
            "app/_generate_sheet.html",
            folder=folder,
            debts=debts,
            generating=False,
            fabric_warning=fabric_service.fabric_vintage_warning(folder.id, session),
        )
    # The tracking row must be committed BEFORE dispatch: task_postrun updates
    # it by task_id, and a fast job can finish before a row inserted after
    # apply_async exists — leaving it PENDING ("Generating…") forever.
    task_id = str(uuid.uuid4())
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=task_id,
        status="PENDING",
        operation_type="Export",
        operation_detail="Generate a submission",
        user_email=me.email,
        organization_id=me.organization_id,
        folder_deadline=folder.deadline,
        session=session,
    )
    generate_submission.apply_async(args=[me.id, folder.id], task_id=task_id)
    # watch=True: if the job already landed (it's near-instant for small
    # filings), this response carries the "Submission ready" modal directly.
    return (
        render_template(
            "app/_submissions_list.html", **_list_context(identity, session, watch=True)
        ),
        (200),
        {"HX-Retarget": "#submissions-list", "HX-Reswap": "outerHTML"},
    )


@bp.route("/submissions/filed", methods=["POST"])
@page_session_required
def mark_filed(identity):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is not None:
        try:
            filing_service.mark_filed(me.id, folder.id, session)
        except ServiceError:
            pass
    return render_template("app/_submissions_list.html", **_list_context(identity, session))


@bp.route("/submissions/reopen", methods=["POST"])
@page_session_required
def reopen(identity):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is not None:
        try:
            filing_service.reopen(me.id, folder.id, session)
        except ServiceError:
            pass
    return render_template("app/_submissions_list.html", **_list_context(identity, session))
