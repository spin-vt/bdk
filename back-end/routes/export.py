"""Export workflow: export a filing, list/download/delete exports."""

import io

from flask import Blueprint, jsonify, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.database_controller import (
    file_ops,
)
from database.sessions import get_session

bp = Blueprint("export", __name__)


@bp.route("/api/downloadexport/<int:fileid>", methods=["GET"])
@jwt_required()
def download_export(fileid):
    fileid = int(fileid)
    session = get_session()
    try:
        identity = get_jwt_identity()
        if not file_ops.file_belongs_to_organization(
            file_id=fileid, user_id=identity["id"], session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a file not belong to your organization",
                }
            ), 400

        fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
        if not fileVal:
            return jsonify({"status": "error", "message": "File not found"}), 404
        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
            downfile, download_name=fileVal.name, as_attachment=True, mimetype="text/csv"
        )
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
