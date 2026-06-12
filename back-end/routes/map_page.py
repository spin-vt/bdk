"""The studio map (/map) — the MapLibre island inside the server-rendered shell.

The boundary contract proven by the SSR map prototype: the server embeds the map's
initial state as a JSON blob (filing, tile URL, layers grouped by technology,
plans for the inspector verbs, persisted edits); the page chrome talks to the
island only through window.BDKMap; the island talks back only through custom
DOM events. Edits restyle instantly client-side and finalize in the background
(the retile watched over a short-lived per-task SSE — closed when done, so it
never holds a browser connection open the way a persistent stream would).

Read-only contexts (a filed filing, an export snapshot via ?folder=) hide
every mutating affordance server-side.
"""

import json
import time

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request

from controllers.database_controller import folder_ops, user_ops
from database.models import celerytaskinfo, kml_data, service_plan
from database.models import editfile as editfile_model
from database.models import file as file_model
from database.sessions import Session, get_session
from routes.app_pages import _inject_chrome, current_folder, page_session_required
from services import edit_service, plan_service
from services.exceptions import ServiceError

bp = Blueprint("map_page", __name__, template_folder="../templates")
bp.context_processor(_inject_chrome)

# The design's fixed technology colors (mirrors bdk.css --tech-* vars).
TECH_COLORS = {
    10: "#7A5AE0",
    40: "#B45309",
    50: "#2A6FDB",
    70: "#0E7C86",
    71: "#0E7C86",
    72: "#0E7C86",
}


def _me_and_folder(identity, session):
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    return me, current_folder(me, session)


def _edit_summary(ef, name_to_tech, plan_names):
    """One line of plain words for an edit: what it did, per technology."""
    if not ef.markers:
        return "excluded an area"
    by_action = {}
    locations = set()
    for m in ef.markers:
        locations.add(m.get("id"))
        techs = sorted(
            {name_to_tech.get(n) for n in (m.get("editedFile") or []) if name_to_tech.get(n)}
        )
        tech_txt = ", ".join(plan_service.TECH_NAMES.get(t, str(t)) for t in techs) or "coverage"
        if m.get("plan_id"):
            label = plan_names.get(m["plan_id"], "a plan")
            by_action.setdefault(f"set {label} on {tech_txt}", 0)
        else:
            by_action.setdefault(f"excluded {tech_txt}", 0)
    return " · ".join(by_action) + f" · {len(locations)} loc"


@bp.route("/map", strict_slashes=False)
@page_session_required
def map_page(identity):
    session = get_session()
    me, current = _me_and_folder(identity, session)
    folder = current
    viewing_snapshot = False

    requested = request.args.get("folder", type=int)
    if requested is not None:
        if not folder_ops.folder_belongs_to_organization(requested, me.id, session):
            return redirect("/map")
        folder = folder_ops.get_folder_with_id(folderid=requested, session=session)
        viewing_snapshot = folder is not None and folder.type == "export"

    if folder is None:
        return render_template("app/map.html", folder=None, config_json="null", edits=[])

    filed = (folder.status or "open") == "filed"
    read_only = viewing_snapshot or filed

    files = (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless")))
        .order_by(file_model.id)
        .all()
    )
    layers = [
        {"name": f.name, "type": f.type, "tech": f.techType}
        for f in files
        if f.name.lower().endswith((".kml", ".geojson"))
    ]
    name_to_tech = {f.name: f.techType for f in files}
    techs = sorted({f.techType for f in files if f.techType is not None})

    plans = (
        session.query(service_plan)
        .filter(service_plan.folder_id == folder.id)
        .order_by(service_plan.is_default.desc(), service_plan.id)
        .all()
    )
    plans_by_tech = {}
    for p in plans:
        plans_by_tech.setdefault(p.tech_code, []).append({"id": p.id, "name": p.name})
    plan_names = {p.id: p.name for p in plans}

    # Absolute counts for the filing card (never ratios).
    from sqlalchemy import distinct, func

    file_ids = [f.id for f in files]
    served_count = (
        (
            session.query(func.count(distinct(kml_data.location_id)))
            .filter(kml_data.file_id.in_(file_ids), kml_data.served.is_(True))
            .scalar()
            or 0
        )
        if file_ids
        else 0
    )

    fabric_present = (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type == "fabric")
        .first()
        is not None
    )

    # Map bounds from the computed locations (open on the data, not the US).
    mnx, mny, mxx, mxy = (
        (
            session.query(
                func.min(kml_data.longitude),
                func.min(kml_data.latitude),
                func.max(kml_data.longitude),
                func.max(kml_data.latitude),
            )
            .filter(kml_data.file_id.in_(file_ids))
            .one()
        )
        if file_ids
        else (None, None, None, None)
    )
    bounds = [[mnx, mny], [mxx, mxy]] if None not in (mnx, mny, mxx, mxy) else None

    edit_rows = []
    exclusion_features = []
    for ef in (
        session.query(editfile_model)
        .filter(editfile_model.folder_id == folder.id)
        .order_by(editfile_model.id)
        .all()
    ):
        edit_rows.append(
            {"id": ef.id, "name": ef.name, "summary": _edit_summary(ef, name_to_tech, plan_names)}
        )
        try:
            feat = json.loads(bytes(ef.data).decode("utf-8"))
            props = feat.get("properties") or {}
            props.update(editfileId=ef.id, name=ef.name)
            feat["properties"] = props
            exclusion_features.append(feat)
        except Exception:
            pass

    import os

    config = {
        "folderId": folder.id,
        "tileUrl": f"/api/tiles/{folder.id}/{{z}}/{{x}}/{{y}}.pbf",
        "basemapStyle": os.getenv("MAPTILE_STREET")
        or os.getenv("NEXT_PUBLIC_DEVELOP_MAPTILE_STREET")
        or None,
        "layers": layers,
        "bounds": bounds,
        "exclusionBoxes": exclusion_features,
        "techs": techs,
        "techNames": {t: plan_service.TECH_NAMES.get(t, str(t)) for t in techs},
        "techColors": {t: TECH_COLORS.get(t, "#565EC1") for t in techs},
        "plansByTech": plans_by_tech,
        "readOnly": read_only,
        "hasFabric": fabric_present,
    }

    return render_template(
        "app/map.html",
        folder=folder,
        config_json=json.dumps(config),
        edits=edit_rows,
        served_count=served_count,
        techs=techs,
        tech_names=config["techNames"],
        tech_colors=config["techColors"],
        fabric_present=fabric_present,
        read_only=read_only,
        viewing_snapshot=viewing_snapshot,
        filed=filed,
        has_files=bool(files),
    )


@bp.route("/map/edit", methods=["POST"])
@page_session_required
def map_edit(identity):
    """Apply a drawn-area edit (exclude and/or set-plan markers) via the real
    edit flow, returning the chain's task id so the island can watch the
    retile and swap tiles in when it lands."""
    session = get_session()
    data = request.get_json(silent=True) or {}
    try:
        task_id = edit_service.apply_edit(
            user_id=identity["id"],
            folderid=data.get("folderid"),
            markers=data.get("markers") or [],
            polygonfeatures=data.get("polygonfeatures") or [],
            session=session,
        )
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
    return jsonify({"status": "success", "task_id": task_id})


@bp.route("/map/location/<int:location_id>")
@page_session_required
def map_location_detail(identity, location_id):
    """What this location actually gets, per covering file: the kml row's
    stamped speeds + the governing plan's name (area-edit marker > file
    assignment > tech default). The point popup's single source of truth —
    ?folder= scopes it to the folder being viewed (a snapshot keeps its own
    stamped values)."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    requested = request.args.get("folder", type=int)
    if requested is not None:
        if not folder_ops.folder_belongs_to_organization(requested, me.id, session):
            return jsonify({"status": "error", "message": "Not your filing"}), 404
        folder = folder_ops.get_folder_with_id(folderid=requested, session=session)
    if folder is None:
        return jsonify({"status": "success", "services": []})
    files = (
        session.query(file_model)
        .filter(file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless")))
        .all()
    )
    by_id = {f.id: f for f in files}
    rows = (
        session.query(kml_data)
        .filter(kml_data.location_id == location_id, kml_data.file_id.in_(by_id.keys()))
        .all()
        if by_id
        else []
    )
    # Area-edit plan overrides for this location: filename → plan_id.
    overrides = {}
    for ef in session.query(editfile_model).filter(editfile_model.folder_id == folder.id).all():
        for m in ef.markers or []:
            try:
                marker_loc = int(m.get("id"))
            except (TypeError, ValueError):
                continue
            if marker_loc == location_id and m.get("plan_id"):
                for n in m.get("editedFile") or []:
                    overrides[n] = m["plan_id"]
    services = []
    for row in rows:
        f = by_id[row.file_id]
        plan = None
        if f.name in overrides:
            plan = (
                session.query(service_plan)
                .filter(service_plan.id == overrides[f.name], service_plan.folder_id == folder.id)
                .one_or_none()
            )
        if plan is None:
            plan = plan_service.resolve_for_file(f, session)
        services.append(
            {
                "file": f.name,
                "tech": f.techType,
                "plan": plan.name if plan else None,
                "down": row.maxDownloadSpeed,
                "up": row.maxUploadSpeed,
            }
        )
    # Stable order (tech, then file) — the popup renders an instant guess and
    # swaps in this answer; identical ordering means no visual reorder.
    services.sort(key=lambda s: (s["tech"] if s["tech"] is not None else 999, s["file"]))
    return jsonify({"status": "success", "services": services})


@bp.route("/map/edit/<int:editfile_id>")
@page_session_required
def map_edit_detail(identity, editfile_id):
    """A saved edit's shape + picks, for the edit-an-edit inspector."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return jsonify({"status": "error", "message": "No filing"}), 404
    try:
        detail = edit_service.get_edit(identity["id"], folder.id, editfile_id, session)
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
    return jsonify({"status": "success", **detail})


@bp.route("/map/edit/<int:editfile_id>/replace", methods=["POST"])
@page_session_required
def map_edit_replace(identity, editfile_id):
    """Replace a saved edit's shape/picks in place; returns the recompute's
    task id so the island can watch it land."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return jsonify({"status": "error", "message": "No filing"}), 404
    data = request.get_json(silent=True) or {}
    try:
        task_id = edit_service.replace_edit(
            user_id=identity["id"],
            folderid=folder.id,
            editfile_id=editfile_id,
            markers=data.get("markers") or [],
            polygonfeature=data.get("polygonfeature"),
            session=session,
        )
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
    return jsonify({"status": "success", "task_id": task_id})


@bp.route("/map/exclusions")
@page_session_required
def map_exclusions(identity):
    """Server truth for the edit-shapes layer, re-fetched after a save so a
    just-created edit is removable without a reload."""
    session = get_session()
    me, folder = _me_and_folder(identity, session)
    if folder is None:
        return jsonify({"status": "success", "features": []})
    features = []
    for ef in session.query(editfile_model).filter(editfile_model.folder_id == folder.id).all():
        try:
            feat = json.loads(bytes(ef.data).decode("utf-8"))
            props = feat.get("properties") or {}
            props.update(editfileId=ef.id, name=ef.name)
            feat["properties"] = props
            features.append(feat)
        except Exception:
            pass
    return jsonify({"status": "success", "features": features})


@bp.route("/map/edit-events/<task_id>")
@page_session_required
def map_edit_events(identity, task_id):
    """A short-lived SSE stream watching ONE task (an edit's retile or an
    undo's recompute): emits `state` ticks and a final `done`, then closes.
    Unlike the persistent jobs stream, this lives only for the operation, so
    it doesn't need visibility gating — but it is capped all the same."""
    session = get_session()
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    owns = (
        session.query(celerytaskinfo)
        .filter(
            celerytaskinfo.task_id == str(task_id),
            celerytaskinfo.organization_id == (me.organization_id if me else -1),
        )
        .first()
        is not None
    )
    if not owns:
        return Response("Not your task", status=403)

    from controllers.celery_controller.celery_config import celery

    app = current_app._get_current_object()
    poll = app.config.get("JOBS_SSE_POLL_SECONDS", 1.0)
    max_ticks = app.config.get("MAP_TASK_SSE_MAX_TICKS", 600)

    def stream():
        terminal = ("SUCCESS", "FAILURE", "REVOKED")
        for _ in range(max_ticks):
            # Celery's result backend is the live truth; the task-info row is
            # the fallback that catches sweep-marked failures (a crashed chain
            # leaves AsyncResult PENDING forever).
            state = celery.AsyncResult(str(task_id)).state
            if state not in terminal:
                db_session = Session()
                try:
                    row = (
                        db_session.query(celerytaskinfo)
                        .filter(celerytaskinfo.task_id == str(task_id))
                        .first()
                    )
                    if row is not None and row.status in terminal:
                        state = row.status
                finally:
                    db_session.close()
            if state in terminal:
                yield f"event: done\ndata: {state}\n\n"
                return
            yield f"event: state\ndata: {state}\n\n"
            if poll:
                time.sleep(poll)
        yield "event: done\ndata: TIMEOUT\n\n"

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Cache-Control"] = "no-cache"
    return resp
