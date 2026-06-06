"""FCC challenge export/submit."""

from datetime import datetime

import shortuuid
from flask import Blueprint, jsonify, request, send_file

from controllers.database_controller import (
    challenge_ops,
)

bp = Blueprint("challenge", __name__)


@bp.route("/api/exportChallenge", methods=["GET"])
def exportChallenge():
    csv_output = challenge_ops.export()
    if csv_output:
        csv_output.seek(0)  # rewind the stream back to the start
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y_%B")
        download_name = "BDC_BulkChallenge_" + formatted_time + "_" + shortuuid.uuid()[:4] + ".csv"
        return send_file(
            csv_output, as_attachment=True, download_name=download_name, mimetype="text/csv"
        )
    else:
        return jsonify({"status": "error"})


@bp.route("/api/submit-challenge", methods=["POST"])
def submit_challenge():
    data = request.json  # This will give you the entire JSON payload
    challenge_ops.writeToDB(data)
    return jsonify({"message": "Data processed!"}), 200
