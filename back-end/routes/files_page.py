"""The files & plans page (/files) — fabric, coverage, and plans tabs.

Server-rendered on the shared `token` session like every redesigned page.
Coverage files and manual edits decide WHERE you serve; plans define WHAT you
sell there. The page reuses the proven flows underneath: fabric intake v2,
the upload dispatch (with a geometry-derived technology guess), the op-4
recompute chain, and the plan service's write-through.
"""

from celery import chain
from flask import Blueprint, redirect, render_template, request

from controllers.celery_controller.celery_tasks import async_delete_files, process_data
from controllers.database_controller import celerytaskinfo_ops, user_ops
from database.models import editfile as editfile_model
from database.models import file as file_model
from database.models import service_plan
from database.sessions import get_session
from routes.app_pages import _inject_chrome, current_folder, page_session_required
from services import fabric_service, plan_service, upload_service
from services.exceptions import ServiceError

bp = Blueprint("files_page", __name__, template_folder="../templates")
# The shared header chrome (theme, filing label, job pill state) is built by
# app_pages' context processor; blueprint context processors are per-blueprint,
# so register the same one here.
bp.context_processor(_inject_chrome)

# File types that appear in the coverage table (fabric roles never do).
COVERAGE_TYPES = ("wired", "wireless")
BUFFER_CHOICES = (50, 100, 150, 200, 250)


def _me_and_folder(identity, session):
    """The logged-in user and their org's current (latest upload) filing."""
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    return me, current_folder(me, session)


def _coverage_files(folder, session):
    return (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type.in_(COVERAGE_TYPES))
        .order_by(file_model.id)
        .all()
    )


def _owned_coverage_file(identity, file_id, session):
    """The coverage file, only if it belongs to the user's current filing."""
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return None, None, None
    f = (
        session.query(file_model)
        .filter(
            file_model.id == file_id,
            file_model.folder_id == folder.id,
            file_model.type.in_(COVERAGE_TYPES),
        )
        .one_or_none()
    )
    return me, folder, f


def _plans(folder, session):
    return (
        session.query(service_plan)
        .filter(service_plan.folder_id == folder.id)
        .order_by(service_plan.id)
        .all()
    )


def _page_context(identity, session, tab, tech_filter=None):
    me, folder = _me_and_folder(identity, session)
    ctx = {
        "tab": tab,
        "tech_filter": tech_filter,
        "folder": folder,
        "wired_techs": plan_service.WIRED_TECHS,
        "wireless_techs": plan_service.WIRELESS_TECHS,
        "tech_names": plan_service.TECH_NAMES,
        "category_labels": plan_service.CATEGORY_LABELS,
        "buffer_choices": BUFFER_CHOICES,
    }
    if folder is None:
        ctx.update(
            fabric=None,
            files=[],
            edits=[],
            plans=[],
            techs_in_use=[],
            fabric_processing=False,
            coverage_processing=False,
        )
        return ctx

    from database.models import celerytaskinfo
    from services.job_service import ACTIVE_STATUSES

    def _busy(op_type):
        return (
            session.query(celerytaskinfo)
            .filter(
                celerytaskinfo.organization_id == me.organization_id,
                celerytaskinfo.operation_type == op_type,
                celerytaskinfo.folder_deadline == folder.deadline,
                celerytaskinfo.status.in_(ACTIVE_STATUSES),
            )
            .first()
            is not None
        )

    ctx["fabric_processing"] = _busy("Fabric")
    ctx["coverage_processing"] = _busy("Upload")

    files = _coverage_files(folder, session)
    plans = _plans(folder, session)
    techs_in_use = sorted({f.techType for f in files if f.techType is not None})
    plans_by_tech = {}
    for p in plans:
        plans_by_tech.setdefault(p.tech_code, []).append(p)
    defaults = {t: plan_service.default_plan_for(folder.id, t, session) for t in techs_in_use}
    usage = {p.id: sum(1 for f in files if f.plan_id == p.id) for p in plans}

    from routes.map_page import _edit_summary

    name_to_tech = {f.name: f.techType for f in files}
    plan_names = {p.id: p.name for p in plans}
    edit_rows = [
        {"id": ef.id, "name": ef.name, "summary": _edit_summary(ef, name_to_tech, plan_names)}
        for ef in (
            session.query(editfile_model)
            .filter(editfile_model.folder_id == folder.id)
            .order_by(editfile_model.id)
            .all()
        )
    ]

    ctx.update(
        fabric=fabric_service.fabric_status(me.id, folder.id, session),
        files=files,
        edits=edit_rows,
        plans=plans,
        plans_by_tech=plans_by_tech,
        techs_in_use=techs_in_use,
        default_plans=defaults,
        plan_usage=usage,
    )
    return ctx


def _dispatch_recompute(me, folder, session, detail, files_changed=None):
    """The shared op-4 chain (recompute + coalesced retile) + its job row, the
    same shape updateNetworkFile and delfiles dispatch."""
    result = process_data.apply_async(args=[folder.id, 4])
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Update",
        operation_detail=detail,
        user_email=me.email,
        organization_id=me.organization_id,
        folder_deadline=folder.deadline,
        session=session,
        files_changed=files_changed,
    )
    return result.task_id


# ------------------------------------------------------------------ the page


@bp.route("/files", strict_slashes=False)
@page_session_required
def files_page(identity):
    session = get_session()
    tab = request.args.get("tab") or "coverage"
    if tab not in ("fabric", "coverage", "plans"):
        tab = "coverage"
    tech_filter = request.args.get("tech", type=int)
    return render_template("app/files.html", **_page_context(identity, session, tab, tech_filter))


def _render_tab(identity, session, tab):
    """A tab's inner fragment, for htmx swaps after a mutation."""
    template = {
        "fabric": "app/_files_fabric.html",
        "coverage": "app/_files_coverage.html",
        "plans": "app/_files_plans.html",
    }[tab]
    return render_template(template, **_page_context(identity, session, tab))


# ------------------------------------------------------------------ fabric


@bp.route("/files/fabric/upload", methods=["POST"])
@page_session_required
def fabric_upload(identity):
    """Add or replace the fabric (zip or CSV). A vintage mismatch is a hard
    warning (409 underneath): the fragment offers an explicit 'Use anyway'
    that re-submits the same form with override=1."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/files")
    upload = request.files.get("fabric_file")
    if upload is None or not upload.filename:
        return render_template("app/_files_fabric_error.html", error="Choose a file first.")
    override = request.form.get("override") == "1"
    try:
        fabric_service.intake_fabric(
            me.id, folder.id, upload.filename, upload.read(), session, override_vintage=override
        )
    except ServiceError as e:
        if e.status == 409:
            return render_template("app/_files_fabric_warn.html", message=e.message)
        return render_template("app/_files_fabric_error.html", error=e.message)
    # The form targets its feedback slot; a successful intake repaints the tab.
    return _render_tab(identity, session, "fabric"), 200, {"HX-Retarget": "#files-tab"}


# ------------------------------------------------------------------ coverage


@bp.route("/files/coverage/upload", methods=["POST"])
@page_session_required
def coverage_upload(identity):
    """Add network files (.kml/.geojson). Geometry decides the technology
    guess — lines → Fiber (50), polygons → Unlicensed FW (70) — corrected with
    one tap in the table afterwards. Fabric CSVs belong on the fabric tab."""
    import json as _json

    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/files")
    uploads = [u for u in request.files.getlist("network_files") if u.filename]
    if not uploads:
        return (
            render_template(
                "app/_files_coverage_note.html", error="Choose one or more files first."
            ),
            200,
            {"HX-Retarget": "#coverage-feedback"},
        )
    raw_files, file_data_list = [], []
    for u in uploads:
        if u.filename.lower().endswith(".csv"):
            return (
                render_template(
                    "app/_files_coverage_note.html",
                    error=f"{u.filename} looks like a fabric CSV — add it on the Fabric tab.",
                ),
                200,
                {"HX-Retarget": "#coverage-feedback"},
            )
        data = u.read()
        guess = upload_service.guess_geometry(u.filename, data)
        if guess["geom"] is None:
            return (
                render_template(
                    "app/_files_coverage_note.html",
                    error=f"We couldn't read {u.filename} as coverage geometry. "
                    "KML and GeoJSON files with lines or polygons work.",
                ),
                200,
                {"HX-Retarget": "#coverage-feedback"},
            )
        raw_files.append((u.filename, data))
        file_data_list.append(
            _json.dumps(
                {
                    "name": u.filename,
                    "downloadSpeed": "0",
                    "uploadSpeed": "0",
                    "techType": str(guess["techType"]),
                    "networkType": guess["type"],
                    "latency": "1",
                    "categoryCode": "X",
                }
            )
        )
    try:
        upload_service.dispatch_upload(
            me.id, folder.id, raw_files, file_data_list, "-1", None, session
        )
    except ServiceError as e:
        return (
            render_template("app/_files_coverage_note.html", error=e.message),
            200,
            {"HX-Retarget": "#coverage-feedback"},
        )
    return _render_tab(identity, session, "coverage")


@bp.route("/files/coverage/<int:file_id>/tech", methods=["POST"])
@page_session_required
def coverage_set_tech(identity, file_id):
    """Change a coverage file's technology. Within the same geometry family it
    writes through (file + kml rows). Crossing families (a lines file to a
    fixed-wireless tech or vice versa) is unusual — without confirm=1 it
    returns the friction modal; confirmed, it changes the compute type and
    dispatches the recompute."""
    from database.models import kml_data

    session = get_session()
    me, folder, f = _owned_coverage_file(identity, file_id, session)
    if f is None:
        return redirect("/files")
    tech = request.form.get("tech", type=int)
    if tech not in plan_service.TECH_NAMES:
        return _render_tab(identity, session, "coverage")
    new_type = "wired" if tech in plan_service.WIRED_TECHS else "wireless"

    if new_type != f.type and request.form.get("confirm") != "1":
        # The select targets the tab; the friction modal goes to the slot.
        return (
            render_template(
                "app/_files_tech_confirm.html",
                f=f,
                tech=tech,
                tech_names=plan_service.TECH_NAMES,
                new_type=new_type,
            ),
            200,
            {"HX-Retarget": "#modal-slot"},
        )

    type_changed = new_type != f.type
    f.techType = tech
    if f.plan_id is not None:
        plan = session.query(service_plan).filter(service_plan.id == f.plan_id).one_or_none()
        if plan is not None and plan.tech_code != tech:
            f.plan_id = None  # plans are per-technology; a cross-tech change clears it
    if type_changed:
        f.type = new_type
        plan_service.restamp_governing_default(f, session)  # the new tech's default governs now
        session.commit()
        _dispatch_recompute(
            me, folder, session, "Update filename or filetype in a filing", files_changed=f.name
        )
    else:
        session.query(kml_data).filter(kml_data.file_id == f.id).update({kml_data.techType: tech})
        plan_service.restamp_governing_default(f, session)
        session.commit()
    return _render_tab(identity, session, "coverage")


@bp.route("/files/coverage/<int:file_id>/plan", methods=["POST"])
@page_session_required
def coverage_set_plan(identity, file_id):
    session = get_session()
    me, folder, f = _owned_coverage_file(identity, file_id, session)
    if f is None:
        return redirect("/files")
    raw = request.form.get("plan_id", "")
    try:
        plan_service.assign_plan_to_file(f.id, int(raw) if raw else None, session)
    except ServiceError:
        pass  # the re-rendered tab shows the unchanged state
    return _render_tab(identity, session, "coverage")


@bp.route("/files/coverage/<int:file_id>/buffer", methods=["POST"])
@page_session_required
def coverage_set_buffer(identity, file_id):
    """The advanced setting: route reach, line (wired) files only. Changing it
    recomputes coverage."""
    session = get_session()
    me, folder, f = _owned_coverage_file(identity, file_id, session)
    if f is None or f.type != "wired":
        return redirect("/files")
    buffer_m = request.form.get("buffer_m", type=int)
    if buffer_m not in BUFFER_CHOICES:
        return _render_tab(identity, session, "coverage")
    if buffer_m != (f.coverage_buffer_m or 100):
        f.coverage_buffer_m = buffer_m
        session.commit()
        _dispatch_recompute(me, folder, session, "Regenerate Map", files_changed=f.name)
    return _render_tab(identity, session, "coverage")


def _dispatch_delete(me, folder, session, file_ids, editfile_ids, names):
    task_chain = chain(
        async_delete_files.s(file_ids=file_ids, editfile_ids=editfile_ids),
        process_data.si(folderid=folder.id, operation=4),
    )
    result = task_chain.apply_async()
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Delete",
        operation_detail="Delete files in a filing",
        user_email=me.email,
        organization_id=me.organization_id,
        folder_deadline=folder.deadline,
        session=session,
        files_changed=", ".join(names),
    )


@bp.route("/files/coverage/<int:file_id>/remove", methods=["POST"])
@page_session_required
def coverage_remove(identity, file_id):
    session = get_session()
    me, folder, f = _owned_coverage_file(identity, file_id, session)
    if f is not None:
        _dispatch_delete(me, folder, session, [f.id], [], [f.name])
    return _render_tab(identity, session, "coverage")


@bp.route("/files/edits/<int:editfile_id>/remove", methods=["POST"])
@page_session_required
def edit_remove(identity, editfile_id):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/files")
    ef = (
        session.query(editfile_model)
        .filter(editfile_model.id == editfile_id, editfile_model.folder_id == folder.id)
        .one_or_none()
    )
    if ef is not None:
        _dispatch_delete(me, folder, session, [], [ef.id], [ef.name])
    return _render_tab(identity, session, "coverage")


# ------------------------------------------------------------------ plans


@bp.route("/files/plans/save", methods=["POST"])
@page_session_required
def plans_save(identity):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/files")
    form = request.form
    plan_id = form.get("plan_id", type=int)
    tech = form.get("tech", type=int)
    use_default_brand = form.get("use_default_brand") == "on"
    try:
        plan_service.save_plan(
            folder.id,
            name=form.get("name", ""),
            tech_code=tech,
            max_download=form.get("down"),
            max_upload=form.get("up"),
            session=session,
            low_latency=form.get("low_latency") == "on",
            category=form.get("category", "X"),
            brand=None if use_default_brand else form.get("brand"),
            is_default=form.get("is_default") == "on",
            plan_id=plan_id,
        )
    except ServiceError as e:
        return render_template(
            "app/_files_plan_modal.html",
            tech=tech if tech in plan_service.TECH_NAMES else list(plan_service.TECH_NAMES)[0],
            plan=None,
            form=form,
            error=e.message,
            techs_with_default=_techs_with_default(folder.id, session, exclude_plan_id=plan_id),
            tech_names=plan_service.TECH_NAMES,
            category_labels=plan_service.CATEGORY_LABELS,
            org_name=me.organization.name if me.organization else "",
            return_tab=form.get("return_tab", "plans"),
        )
    resp = render_template("app/_files_modal_close.html")
    return resp, 200, {"HX-Redirect": f"/files?tab={form.get('return_tab', 'plans')}"}


# ------------------------------------------------------------------ modals


def _techs_with_default(folder_id, session, exclude_plan_id=None):
    """Tech codes that already have a default plan (optionally not counting
    the plan being edited) — drives the modal's set-as-default auto-check."""
    q = session.query(service_plan.tech_code).filter(
        service_plan.folder_id == folder_id, service_plan.is_default.is_(True)
    )
    if exclude_plan_id is not None:
        q = q.filter(service_plan.id != exclude_plan_id)
    return sorted({t for (t,) in q})


@bp.route("/files/modals/plan")
@page_session_required
def plan_modal(identity):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/files")
    tech = request.args.get("tech", type=int)
    plan_id = request.args.get("plan_id", type=int)
    plan = None
    if plan_id:
        plan = (
            session.query(service_plan)
            .filter(service_plan.id == plan_id, service_plan.folder_id == folder.id)
            .one_or_none()
        )
        if plan is not None:
            tech = plan.tech_code
    defaults = _techs_with_default(folder.id, session, exclude_plan_id=plan.id if plan else None)
    if tech not in plan_service.TECH_NAMES:
        # No ?tech (the global "+ another plan" button): preselect the first
        # tech in use still missing its default, else the first tech.
        in_use = sorted(
            {f.techType for f in _coverage_files(folder, session) if f.techType is not None}
        )
        missing = [t for t in in_use if t not in defaults]
        tech = (missing or in_use or list(plan_service.TECH_NAMES))[0]
    return render_template(
        "app/_files_plan_modal.html",
        tech=tech,
        plan=plan,
        form=None,
        error=None,
        default_checked=(plan.is_default if plan is not None else tech not in defaults),
        techs_with_default=defaults,
        tech_names=plan_service.TECH_NAMES,
        category_labels=plan_service.CATEGORY_LABELS,
        org_name=me.organization.name if me.organization else "",
        return_tab=request.args.get("return_tab", "plans"),
    )


@bp.route("/files/modals/buffer/<int:file_id>")
@page_session_required
def buffer_modal(identity, file_id):
    session = get_session()
    me, folder, f = _owned_coverage_file(identity, file_id, session)
    if f is None or f.type != "wired":
        return redirect("/files")
    return render_template("app/_files_buffer_modal.html", f=f, buffer_choices=BUFFER_CHOICES)


@bp.route("/files/modals/none")
@page_session_required
def modal_none(identity):
    return render_template("app/_files_modal_close.html")
