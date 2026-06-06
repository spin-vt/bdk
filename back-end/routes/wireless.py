"""Wireless signal-propagation: coverage compute, rasters, towers, prediction."""

import io
import json
import os

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    preview_fabric_locaiton_coverage,
    raster2vector,
    run_signalserver,
)
from controllers.database_controller.tower_ops import create_tower, get_tower_with_towername
from controllers.database_controller.towerinfo_ops import create_towerinfo
from controllers.signalserver_controller.read_towerinfo import read_tower_csv
from controllers.signalserver_controller.signalserver_command_builder import runsig_command_builder
from database.sessions import get_session
from utils.logger_config import logger
from utils.namingschemes import (
    SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE,
)

bp = Blueprint("wireless", __name__)


@bp.route("/api/compute-wireless-coverage", methods=["POST"])
@jwt_required()
def compute_wireless_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        towerVal = create_tower(towername=data["towername"], userid=identity["id"])
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            logger.debug(towerVal)
            return jsonify({"error": towerVal}), 400
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(
            username=identity["username"], towername=data["towername"]
        )
        del data["towername"]
        command = runsig_command_builder(data, outfile_name)
        data["tower_id"] = towerVal.id

        tower_info_val = create_towerinfo(tower_info_data=data)
        if isinstance(tower_info_val, str):  # In case create_towerinfo returned an error message
            logger.debug(tower_info_val)
            return jsonify({"error": tower_info_val}), 400

        task = run_signalserver.apply_async(
            args=[command, outfile_name, towerVal.id, data]
        )  # store the AsyncResult instance
        return jsonify(
            {"status": "success", "task_id": task.id}
        ), 200  # return task id to the client
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-raster-image/<string:towername>", methods=["GET"])
@jwt_required()
def get_raster_image(towername):
    session = get_session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(
            tower_name=towername, user_id=identity["id"], session=session
        )
        if isinstance(towerVal, str):  # In case create_tower returned an error
            logger.debug(towerVal)
            return jsonify({"status": "error", "message": towerVal}), 400

        if not towerVal:
            logger.debug("tower not found under towername")
            return jsonify({"error": "File not found"}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            image_io = io.BytesIO(rasterData.image_data)
            image_io.seek(0)
            response = send_file(image_io, mimetype="image/png")
            return response
        else:
            return jsonify({"status": "error", "message": "Raster data not found"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-transparent-raster-image/<string:towername>", methods=["GET"])
@jwt_required()
def get_transparent_raster_image(towername):
    session = get_session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(
            tower_name=towername, user_id=identity["id"], session=session
        )
        if isinstance(towerVal, str):  # In case create_tower returned an error
            logger.debug(towerVal)
            return jsonify({"error": towerVal}), 400

        if not towerVal:
            logger.debug("tower not found under towername")
            return jsonify({"status": "error", "message": "File not found"}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            image_io = io.BytesIO(rasterData.transparent_image_data)
            image_io.seek(0)
            response = send_file(image_io, mimetype="image/png")
            return response
        else:
            return jsonify({"status": "error", "message": "Raster data not found"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-raster-bounds/<string:towername>", methods=["GET"])
@jwt_required()
def get_raster_bounds(towername):
    session = get_session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(
            tower_name=towername, user_id=identity["id"], session=session
        )
        if isinstance(towerVal, str):  # In case create_tower returned an error message
            logger.debug(towerVal)
            return jsonify({"status": "error", "message": towerVal}), 400

        if not towerVal:
            return jsonify({"status": "error", "message": "File not found"}), 404

        rasterData = towerVal.raster_data
        if rasterData:
            bounds = {
                "north": rasterData.north_bound,
                "south": rasterData.south_bound,
                "east": rasterData.east_bound,
                "west": rasterData.west_bound,
            }
            return jsonify({"status": "success", "bounds": bounds}), 200
        else:
            return jsonify({"status": "error", "message": "Raster data not found"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-loss-color-mapping/<string:towername>", methods=["GET"])
@jwt_required()
def get_loss_color_mapping(towername):
    session = get_session()
    try:
        identity = get_jwt_identity()
        towerVal = get_tower_with_towername(
            tower_name=towername, user_id=identity["id"], session=session
        )
        if not towerVal:
            logger.debug("Tower not found under towername")
            return jsonify({"status": "error", "messsage": "Mapping not found"}), 404

        rasterData = towerVal.raster_data
        if rasterData and rasterData.loss_color_mapping:
            # Now we can just return the JSON directly
            return jsonify(rasterData.loss_color_mapping), 200
        else:
            return jsonify({"status": "error", "message": "Loss to color mapping not found"}), 404

    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/upload-tower-csv", methods=["POST"])
@jwt_required()
def upload_csv():
    try:
        identity = get_jwt_identity()
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "No selected file"}), 400

        if file and file.filename.endswith(".csv"):
            # Read the file content
            tower_data = read_tower_csv(file)
            if not isinstance(tower_data, str):
                return jsonify(tower_data), 200
            else:
                return jsonify({"status": "error", "message": tower_data}), 400
        else:
            return jsonify({"status": "error", "message": "Invalid CSV file"}), 400
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/compute-wireless-prediction-fabric-coverage", methods=["POST"])
@jwt_required()
def compute_wireless_prediction_fabric_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(
            username=identity["username"], towername=data["towername"]
        )
        task = raster2vector.apply_async(
            args=[data, identity["id"], outfile_name]
        )  # store the AsyncResult instance
        kml_filename = outfile_name + ".kml"
        return jsonify(
            {"status": "success", "task_id": task.id, "kml_filename": kml_filename}
        ), 200  # return task id to the client
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/preview-wireless-prediction-fabric-coverage", methods=["POST"])
@jwt_required()
def preview_wireless_prediction_fabric_coverage():
    try:
        identity = get_jwt_identity()
        data = request.json
        outfile_name = SIGNALSERVER_RASTER_DATA_NAME_TEMPLATE.format(
            username=identity["username"], towername=data["towername"]
        )
        task = preview_fabric_locaiton_coverage.apply_async(
            args=[data, identity["id"], outfile_name]
        )  # store the AsyncResult instance
        kml_filename = outfile_name + ".kml"
        return jsonify(
            {"status": "success", "task_id": task.id, "kml_filename": kml_filename}
        ), 200  # return task id to the client
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/get-preview-geojson/<string:filename>", methods=["GET"])
@jwt_required()
def get_preview_geojson(filename):
    try:
        identity = get_jwt_identity()
        with open(filename) as file:
            geojson_data = json.load(file)  # Read and parse the JSON file
        os.remove(filename)
        return jsonify(geojson_data)  # Return the JSON data
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
