"""Map editing: toggle markers and edit-geojson reads."""

import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError
from shapely.geometry import shape

from controllers.celery_controller.celery_tasks import (
    toggle_tiles,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    editfile_ops,
    folder_ops,
    user_ops,
)
from database.sessions import get_session
from utils.logger_config import logger

bp = Blueprint("edit", __name__)


@bp.route("/api/toggle-markers", methods=["POST"])
@jwt_required()
def toggle_markers():
    try:
        identity = get_jwt_identity()
        session = get_session()
        request_data = request.json
        markers = request_data["marker"]
        folderid = request_data["folderid"]
        polygonfeatures = request_data["polygonfeatures"]
        if folderid == -1:
            return jsonify({"status": "error", "message": "Invalid folder id"}), 400

        userVal = user_ops.get_user_with_id(identity["id"], session=session)

        if not userVal.verified:
            return jsonify(
                {
                    "status": "error",
                    "message": "Please Verify your email to start working on a filing",
                }
            ), 400
        if not userVal.organization_id:
            return jsonify(
                {
                    "status": "error",
                    "message": "Create or join an organization to start working on a filing",
                }
            ), 400
        if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)

        # Filter out points where editedFile is empty
        filtered_markers = []
        for polygon in markers:
            filtered_polygon = [
                point for point in polygon if point["editedFile"] and len(point["editedFile"]) > 0
            ]
            if filtered_polygon:
                filtered_markers.append(filtered_polygon)

        if len(filtered_markers) == 0:
            return jsonify({"status": "error", "message": "No valid edits submitted"}), 400

        # Generate concatenated_filenames
        all_filenames = set()
        for polygon in filtered_markers:
            for point in polygon:
                all_filenames.update(point["editedFile"])
        concatenated_filenames = ", ".join(sorted(all_filenames))
        logger.debug(polygonfeatures)
        result = toggle_tiles.apply_async(args=[filtered_markers, folderid, polygonfeatures])

        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Edit",
            operation_detail="Edit a filing",
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=folderVal.deadline,
            session=session,
            files_changed=concatenated_filenames,
        )
        return jsonify({"status": "success"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-edit-geojson/<int:fileid>", methods=["GET"])
@jwt_required()
def get_edit_geojson(fileid):
    session = get_session()
    try:
        identity = get_jwt_identity()
        fileid = int(fileid)
        if not editfile_ops.editfile_belongs_to_organization(
            file_id=fileid, user_id=identity["id"], session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a file not belong to your organization",
                }
            ), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)

        if editfile is None:
            return jsonify({"status": "error", "message": "File not found"}), 404

        # Decode the binary data to string assuming it's stored in UTF-8 encoded JSON format
        geojson_data = json.loads(editfile.data.decode("utf-8"))
        return jsonify(geojson_data), 200
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-edit-geojson-centroid/<int:fileid>", methods=["GET"])
@jwt_required()
def get_edit_geojson_centroid(fileid):
    session = get_session()
    try:
        identity = get_jwt_identity()
        if not editfile_ops.editfile_belongs_to_organization(
            file_id=fileid, user_id=identity["id"], session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a file not belong to your organization",
                }
            ), 400

        editfile = editfile_ops.get_editfile_with_id(fileid=fileid, session=session)

        if editfile is None:
            return jsonify({"status": "error", "message": "File not found"}), 400

        # Decode the binary data to a JSON object
        geojson_object = json.loads(editfile.data.decode("utf-8"))

        # Calculate the centroid of the polygon
        polygon = shape(geojson_object["geometry"])
        centroid = polygon.centroid
        centroid_coords = {"latitude": centroid.y, "longitude": centroid.x}
        # Include centroid coordinates in the response
        return jsonify(centroid_coords), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        return jsonify(
            {"status": "error", "message": "Failed to fetch file", "details": str(e)}
        ), 500
