"""Map editing: toggle markers and edit-geojson reads."""

import json

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError
from shapely.geometry import shape

from controllers.database_controller import (
    editfile_ops,
)
from database.sessions import get_session

bp = Blueprint("edit", __name__)


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
