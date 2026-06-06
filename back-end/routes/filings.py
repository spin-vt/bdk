"""Filings: upload/submit, served data, folders, search, delete filing."""

import base64
import json
import os
from datetime import datetime

from celery import chain
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    add_files_to_folder,
    async_folder_copy_for_import,
    async_folder_delete,
    process_data,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    fabric_ops,
    folder_ops,
    kml_ops,
    user_ops,
)
from database.sessions import get_session
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
            return jsonify({"error": "Filling ID is invalid"}), 400
        else:
            if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
                return jsonify(
                    {"error": "You are accessing a filing not belong to your organization"}
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

        operation_detail = "Added more files to a filing"
        file_data_list = request.form.getlist("fileData")
        filenames = []
        for file_data_str in file_data_list:
            try:
                file_data = json.loads(file_data_str)  # Decode JSON string to Python dictionary
                filename, file_extension = os.path.splitext(file_data["name"])
                if file_extension not in [".csv", ".kml", ".geojson"]:
                    return jsonify(
                        {
                            "status": "error",
                            "message": "Invalid file extension. Allowed extensions are .csv, .kml, and .geojson",
                        }
                    ), 400

                if not file_data["name"].endswith(".csv"):  # Validate speeds only for non-csv files
                    try:
                        # Parse speeds as integers
                        download_speed = int(file_data["downloadSpeed"])
                        upload_speed = int(file_data["uploadSpeed"])
                    except (ValueError, KeyError):
                        return jsonify(
                            {
                                "status": "error",
                                "message": "Please enter valid integer values for download and upload speeds",
                            }
                        ), 400
                    try:
                        latency = int(file_data["latency"])
                        techType = int(file_data["techType"])
                    except (ValueError, KeyError):
                        return jsonify(
                            {
                                "status": "error",
                                "message": "Please enter valid values for latency and techTypes",
                            }
                        ), 400

                filenames.append(file_data["name"])  # Collect the filename
            except json.JSONDecodeError:
                return jsonify(
                    {"status": "error", "message": "Invalid JSON format in file data"}
                ), 400

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
        import_folder_id = int(request.form.get("importFolder"))
        # Prepare data for the task
        file_contents = [
            (f.filename, base64.b64encode(f.read()).decode("utf-8"), data)
            for f, data in zip(files, file_data_list)
        ]
        if folderid == -1:
            deadline = request.form.get("deadline")
            if not deadline:
                return jsonify(
                    {"status": "error", "message": "operation failed, no deadline provided"}
                ), 400

            # Attempt to parse the deadline to ensure it's valid
            try:
                deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"status": "error", "message": "invalid deadline format"}), 400

            if import_folder_id != -1:
                if not folder_ops.folder_belongs_to_organization(
                    import_folder_id, identity["id"], session
                ):
                    return jsonify(
                        {
                            "status": "error",
                            "message": "Operation failed because you are accessing a filing not belong to your organization",
                        }
                    ), 400
                # Asynchronous copy and create new folder with deadline
                logger.info(
                    "In operation 3 of upload: create a new filing by importing from previous filings"
                )
                task_chain = chain(
                    async_folder_copy_for_import.s(import_folder_id, deadline_date),
                    add_files_to_folder.s(file_contents=file_contents),
                    process_data.s(operation=3),
                )

                import_folderval = folder_ops.get_folder_with_id(import_folder_id, session=session)
                operation_detail = f"Create a new Filing by importing from filing with deadline {import_folderval.deadline.strftime('%Y-%m')}"

            else:
                # Create new folder with deadline
                logger.info("In operation 2 of upload: create a new filing from scratch")
                new_folder_name = f"Filing for Deadline {deadline_date}"
                folderVal = folder_ops.create_folder(
                    new_folder_name, userVal.organization_id, deadline_date, "upload", session
                )
                session.commit()

                task_chain = chain(
                    add_files_to_folder.s(folderVal.id, file_contents),
                    process_data.si(folderid=folderVal.id, operation=2),
                )

                operation_detail = "Create a new filing"

        else:
            logger.info("In operation 1 of upload: adding more files to a filing")
            if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
                return jsonify(
                    {
                        "status": "error",
                        "message": "Operation failed because you are accessing a filing not belong to your organization",
                    }
                ), 400
            task_chain = chain(
                add_files_to_folder.s(folderid, file_contents),
                process_data.si(folderid=folderid, operation=1),
            )

            operation_detail = "Add more files to a filing"

        result = task_chain.apply_async()

        if folderid != -1:
            folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
            deadline = folderVal.deadline
        else:
            deadline_str = request.form.get("deadline")
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()

        concatenated_filenames = ", ".join(filenames)
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Upload",
            operation_detail=operation_detail,
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=deadline,
            session=session,
            files_changed=concatenated_filenames,
        )
        return jsonify(
            {"status": "success", "task_id": result.id}
        ), 200  # return task id to the client

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
                    {"error": "You are accessing a filing not belong to your organization"}
                ), 400

            results_dict = fabric_ops.address_query(folderid, query, session)
            return jsonify(results_dict)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
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
        result = async_folder_delete.apply_async(args=[folderid])
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Delete",
            operation_detail="Delete a filing",
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=deadline,
            session=session,
        )
        return jsonify({"status": "success"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
