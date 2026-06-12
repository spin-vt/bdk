"""The setup page (/setup) — the funnel into everything else.

Two dashed doors (network files / the FCC fabric), either order, drag-drop;
works network-only ("you can see your map before everything's perfect");
a "Building your map…" card while the compute runs; the carry-forward
welcome for a carried filing that just needs its new fabric; and the
returning-filer redirect straight to the map once a filing is fully set up.

Uploads delegate to the SAME services the files page uses (fabric intake v2,
the op-1 upload chain) — setup is a different front door onto proven paths.
A fresh org's first visit starts its window's filing (the explicit
filing_service.start_next_filing, empty for a first-timer).
"""

from flask import Blueprint, redirect, render_template, request

from controllers.database_controller import user_ops
from database.models import celerytaskinfo
from database.models import file as file_model
from database.sessions import get_session
from routes.app_pages import FILING_COOKIE, _inject_chrome, current_folder, page_session_required
from services import fabric_service, filing_service, upload_service
from services.exceptions import ServiceError
from services.job_service import ACTIVE_STATUSES

bp = Blueprint("setup_page", __name__, template_folder="../templates")
bp.context_processor(_inject_chrome)


def _me_and_folder(identity, session):
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    return me, current_folder(me, session)


def _busy(me, folder, session):
    return (
        session.query(celerytaskinfo)
        .filter(
            celerytaskinfo.organization_id == me.organization_id,
            celerytaskinfo.operation_type.in_(("Fabric", "Upload", "Update")),
            celerytaskinfo.folder_deadline == folder.deadline,
            celerytaskinfo.status.in_(ACTIVE_STATUSES),
        )
        .first()
        is not None
    )


def _stage_context(identity, session):
    me, folder = _me_and_folder(identity, session)
    if me is None or me.organization_id is None:
        return {"mode": "no_org"}
    if folder is None:
        return {"mode": "no_filing"}

    files = (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless")))
        .order_by(file_model.id)
        .all()
    )
    fabric = (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type == "fabric")
        .first()
    )
    carried = folder.source_folder_id is not None
    busy = _busy(me, folder, session)
    plans = folder.service_plans
    edits = folder.editfiles

    mode = "doors"
    if busy:
        mode = "building"
    elif carried and fabric is None:
        mode = "carry"
    return {
        "mode": mode,
        "folder": folder,
        "files": files,
        "fabric_file": fabric,
        "carried": carried,
        "plan_count": len(plans),
        "edit_count": len(edits),
        "provider_set": bool(me.organization.provider_id),
        "can_continue": bool(files or fabric),
    }


@bp.route("/setup", strict_slashes=False)
@page_session_required
def setup(identity):
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if me is None or me.organization_id is None:
        return render_template("app/setup.html", **{"mode": "no_org"})
    started_id = None
    if folder is None:
        # First visit with no filing: start the window's filing so the doors
        # have a home (empty for a first-timer; one filing per org per window).
        try:
            folder = filing_service.start_next_filing(identity["id"], session)
            started_id = folder.id
        except ServiceError as e:
            return render_template("app/setup.html", **{"mode": "error", "error": e.message})
    ctx = _stage_context(identity, session)
    # A fully set-up filing doesn't need setup — land on the map (the
    # returning-filer landing; a filed filing renders read-only there).
    if ctx["mode"] == "doors" and ctx.get("fabric_file") is not None and ctx.get("files"):
        return redirect("/map")
    resp = render_template("app/setup.html", **ctx)
    if started_id is not None:
        from flask import make_response

        r = make_response(resp)
        r.set_cookie(FILING_COOKIE, str(started_id), samesite="Lax")
        return r
    return resp


@bp.route("/setup/stage")
@page_session_required
def setup_stage(identity):
    """The stage fragment; polled while the compute runs."""
    session = get_session()
    return render_template("app/_setup_stage.html", **_stage_context(identity, session))


@bp.route("/setup/network", methods=["POST"])
@page_session_required
def setup_network(identity):
    """The network door: same guess-and-dispatch as the files page."""
    import json as _json

    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/setup")
    uploads = request.files.getlist("network_files")
    uploads = [u for u in uploads if u and u.filename]
    if not uploads:
        return render_template("app/_setup_stage.html", **_stage_context(identity, session))
    raw_files, file_data_list = [], []
    error = None
    for u in uploads:
        data = u.read()
        guess = upload_service.guess_geometry(u.filename, data)
        if u.filename.lower().endswith(".csv"):
            error = f"{u.filename} looks like a fabric CSV — use the fabric door."
            continue
        if guess["geom"] is None:
            error = f"Couldn't read {u.filename} — KML or GeoJSON only for now."
            continue
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
    if raw_files:
        try:
            upload_service.dispatch_upload(
                me.id, folder.id, raw_files, file_data_list, "-1", None, session
            )
        except ServiceError as e:
            error = e.message
    ctx = _stage_context(identity, session)
    ctx["error"] = error
    return render_template("app/_setup_stage.html", **ctx)


@bp.route("/setup/fabric", methods=["POST"])
@page_session_required
def setup_fabric(identity):
    """The fabric door: intake v2, with the same overridable vintage warning."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return redirect("/setup")
    upload = request.files.get("fabric_file")
    if upload is None or not upload.filename:
        return render_template("app/_setup_stage.html", **_stage_context(identity, session))
    override = request.form.get("override") == "1"
    error = warn = None
    try:
        fabric_service.intake_fabric(
            me.id, folder.id, upload.filename, upload.read(), session, override_vintage=override
        )
    except ServiceError as e:
        if e.status == 409:
            warn = e.message
        else:
            error = e.message
    ctx = _stage_context(identity, session)
    ctx["error"] = error
    ctx["vintage_warn"] = warn
    return render_template("app/_setup_stage.html", **ctx)
