"""Filings: upload/submit, served data, folders, search, delete filing."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.database_controller import (
    fabric_ops,
    folder_ops,
    kml_ops,
    user_ops,
)
from database.sessions import get_session
from services import filing_service, upload_service
from services.audit import log_action
from services.exceptions import ServiceError
from utils.logger_config import logger

bp = Blueprint("filings", __name__)


@bp.route("/api/served-data/<folderid>", methods=["GET"])
@jwt_required()
def get_number_records(folderid):
    folderid = int(folderid)
    session = get_session()
    try:
        identity = get_jwt_identity()
        if folderid < 0:
            return jsonify({"status": "error", "message": "Filling ID is invalid"}), 400
        else:
            if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
                return jsonify(
                    {
                        "status": "error",
                        "message": "You are accessing a filing not belong to your organization",
                    }
                ), 400

            return jsonify(kml_ops.get_kml_data(folderid=folderid, session=session)), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/submit-data/<folderid>", methods=["POST", "GET"])
@jwt_required()
def submit_data(folderid):
    session = get_session()
    try:
        identity = get_jwt_identity()
        folderid = int(folderid)

        if "file" not in request.files:
            return jsonify({"status": "error", "message": "no file uploaded"}), 400

        files = request.files.getlist("file")
        if len(files) <= 0:
            return jsonify({"status": "error", "message": "no file uploaded"}), 400

        raw_files = [(f.filename, f.read()) for f in files]
        file_data_list = request.form.getlist("fileData")
        result_id = upload_service.dispatch_upload(
            user_id=identity["id"],
            folderid=folderid,
            raw_files=raw_files,
            file_data_list=file_data_list,
            import_folder_raw=request.form.get("importFolder"),
            deadline_raw=request.form.get("deadline"),
            session=session,
        )
        log_action(
            "upload",
            user_id=identity["id"],
            resource_type="folder",
            resource_id=folderid,
            details={"task_id": result_id, "file_count": len(raw_files)},
        )
        return jsonify({"status": "success", "task_id": result_id}), 200  # return task id

    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except ValueError as ve:
        # Handle specific errors, e.g., value errors
        logger.debug(ve)
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        # General catch-all for other exceptions
        logger.debug(e)
        session.rollback()  # Rollback the session in case of error
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api")
def home():
    response_body = {"name": "Success!", "message": "Backend successfully connected to frontend"}

    return response_body


@bp.route("/api/search/<folderid>", methods=["GET"])
@jwt_required()
def search_location(folderid):
    query = request.args.get("query").upper()
    folderid = int(folderid)
    try:
        identity = get_jwt_identity()
        session = get_session()
        try:
            userVal = user_ops.get_user_with_id(identity["id"], session)
            if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
                return jsonify(
                    {
                        "status": "error",
                        "message": "You are accessing a filing not belong to your organization",
                    }
                ), 400

            results_dict = fabric_ops.address_query(folderid, query, session)
            return jsonify(results_dict)
        except Exception as e:
            session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/folders-with-deadlines", methods=["GET"])
@jwt_required()
def get_folders_with_deadlines():
    try:
        identity = get_jwt_identity()
        user_id = identity["id"]
        session = get_session()
        userVal = user_ops.get_user_with_id(userid=user_id, session=session)
        folders = folder_ops.get_folders_by_type_for_org(userVal.organization_id, "upload", session)

        folder_info = [
            {
                "folder_id": folder.id,
                "name": folder.name,
                "deadline": folder.deadline.strftime("%Y-%m-%d") if folder.deadline else None,
            }
            for folder in folders
        ]

        return jsonify(folder_info), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@bp.route("/api/get-last-upload-folder", methods=["GET"])
@jwt_required()
def get_last_folder():
    try:
        identity = get_jwt_identity()
        session = get_session()
        user_id = identity["id"]
        userVal = user_ops.get_user_with_id(userid=user_id, session=session)
        # Hackey way to use this method to get the lastest filing of user
        folderVal = folder_ops.get_upload_folder(orgid=userVal.organization_id, session=session)
        if not folderVal:
            folderid = -1
        else:
            folderid = folderVal.id
        return jsonify(folderid), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api/delfiling", methods=["DELETE"])
@jwt_required()
def delete_filing():
    session = get_session()
    try:
        identity = get_jwt_identity()
        folderid = request.json["folderID"]
        filing_service.delete_filing(user_id=identity["id"], folderid=folderid, session=session)
        log_action(
            "filing_delete",
            user_id=identity["id"],
            resource_type="folder",
            resource_id=folderid,
        )
        return jsonify({"status": "success"}), 200
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
