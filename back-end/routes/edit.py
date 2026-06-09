"""Map editing: toggle markers and edit-geojson reads."""

import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError
from shapely.geometry import shape

from controllers.database_controller import (
    editfile_ops,
)
from database.sessions import get_session
from services import edit_service
from services.audit import log_action
from services.exceptions import ServiceError

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
        edit_service.apply_edit(
            user_id=identity["id"],
            folderid=folderid,
            markers=markers,
            polygonfeatures=polygonfeatures,
            session=session,
        )
        log_action(
            "edit",
            user_id=identity["id"],
            resource_type="folder",
            resource_id=folderid,
            details={"marker_count": len(markers) if hasattr(markers, "__len__") else None},
        )
        return jsonify({"status": "success"}), 200
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
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
