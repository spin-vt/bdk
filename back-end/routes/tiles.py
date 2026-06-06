"""Vector tile serving and map regeneration."""

from flask import Blueprint, Response, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    process_data,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    folder_ops,
    user_ops,
    vt_ops,
)
from database.sessions import get_session

bp = Blueprint("tiles", __name__)


@bp.route("/api/tiles/<folder_id>/<zoom>/<x>/<y>.pbf")
@jwt_required()
def serve_tile_with_folderid(folder_id, zoom, x, y):
    if not folder_id:
        return Response("No tile found", status=404)
    try:
        folder_id = int(folder_id)
    except ValueError:
        return Response("No tile found", status=404)
    if folder_id == -1:
        return Response("No tile found", status=404)

    identity = get_jwt_identity()

    session = get_session()
    if not folder_ops.folder_belongs_to_organization(folder_id, identity["id"], session):
        return jsonify(
            {
                "status": "error",
                "message": "You are accessing a filing not belong to your organization",
            }
        ), 400

    zoom = int(zoom)
    x = int(x)
    y = int(y)
    y = (2**zoom - 1) - y

    tile = vt_ops.retrieve_tiles(zoom, x, y, folder_id)

    if tile is None:
        return Response("No tile found", status=404)

    response = make_response(bytes(tile[0]))
    response.headers["Content-Type"] = "application/x-protobuf"
    response.headers["Content-Encoding"] = "gzip"
    return response


@bp.route("/api/regenerate_map", methods=["POST"])
@jwt_required()
def regenerate_map():
    session = get_session()
    try:
        identity = get_jwt_identity()
        request_data = request.json
        folderid = request_data["folderID"]
        if not folder_ops.folder_belongs_to_organization(
            folder_id=folderid, user_id=identity["id"], session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)
        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
        result = process_data.apply_async(args=[folderid, 4])
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Update",
            operation_detail="Regenerate Map",
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=deadline,
            session=session,
        )
        return jsonify({"status": "success"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
