"""Coverage/edit/network files: list, update, delete, download."""

import io
import os

from celery import chain
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    async_delete_files,
    process_data,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    editfile_ops,
    file_ops,
    folder_ops,
    kml_ops,
    user_ops,
)
from database.sessions import Session
from utils.logger_config import logger

bp = Blueprint("files", __name__)


@bp.route("/api/files", methods=["GET"])
@jwt_required()
def get_files():
    try:
        identity = get_jwt_identity()
        # Verify user own this folder
        session = Session()
        try:
            folder_ID = int(request.args.get("folder_ID"))
        except ValueError:
            return jsonify({"status": "error", "message": "folderID must be integer"}), 400

        if not folder_ops.folder_belongs_to_organization(folder_ID, identity["id"], session):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        if folder_ID:
            filesinfo = file_ops.get_filesinfo_in_folder(folder_ID, session=session)
            return jsonify(filesinfo), 200
        else:
            return jsonify({"status": "error", "message": "Invalid request"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    finally:
        session.close()


@bp.route("/api/editfiles", methods=["GET"])
@jwt_required()
def get_editfiles():
    try:
        identity = get_jwt_identity()
        # Verify user own this folder
        folder_ID = int(request.args.get("folder_ID"))
        session = Session()

        if not folder_ops.folder_belongs_to_organization(folder_ID, identity["id"], session):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        if folder_ID:
            filesinfo = editfile_ops.get_editfilesinfo_in_folder(folder_ID, session=session)

            return jsonify(filesinfo), 200
        else:
            return jsonify({"status": "error", "message": "Invalid request"}), 404
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    finally:
        session.close()


@bp.route("/api/networkfiles/<int:folder_id>", methods=["GET"])
@jwt_required()
def get_network_files(folder_id):
    try:
        identity = get_jwt_identity()
        session = Session()

        folder_id = int(folder_id)

        if not folder_ops.folder_belongs_to_organization(folder_id, identity["id"], session):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        files = file_ops.get_all_network_files_for_fileinfoedit_table(folder_id, session)
        files_data = []
        for file in files:
            filename_without_extension = os.path.splitext(file.name)[0]
            file_info = {
                "id": file.id,
                "name": filename_without_extension,
                "type": file.type,
                "maxDownloadSpeed": file.maxDownloadSpeed,
                "maxUploadSpeed": file.maxUploadSpeed,
                "techType": file.techType,
                "latency": file.latency,
                "category": file.category,
            }

            files_data.append(file_info)
        return jsonify({"status": "success", "files_data": files_data})
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        session.close()


@bp.route("/api/updateNetworkFile/<int:file_id>", methods=["POST"])
@jwt_required()
def update_network_file(file_id):
    try:
        data = request.json
        identity = get_jwt_identity()
        session = Session()
        file_id = int(file_id)

        if not file_ops.file_belongs_to_organization(
            file_id=file_id, user_id=identity["id"], session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a filing not belong to your organization",
                }
            ), 400

        file = file_ops.get_file_with_id(file_id, session)
        if not file:
            return jsonify({"status": "error", "message": "File not found"}), 400

        try:
            int(data["maxDownloadSpeed"]) if "maxDownloadSpeed" in data else file.maxDownloadSpeed
            int(data["maxUploadSpeed"]) if "maxUploadSpeed" in data else file.maxUploadSpeed
        except ValueError:
            return jsonify(
                {
                    "status": "error",
                    "message": "maxDownloadSpeed and maxUploadSpeed must be integers",
                }
            ), 400

        try:
            int(data["latency"]) if "latency" in data else file.latency
            int(data["techType"]) if "techType" in data else file.techType
        except ValueError:
            return jsonify(
                {"status": "error", "message": "Please select valid tech types and latency"}
            ), 400

        logger.debug(data)
        lowercase_type = data["type"].lower()
        if lowercase_type not in ["wired", "wireless"]:
            return jsonify({"status": "error", "message": "Please select a valid type"}), 400
        name_or_type_changed = False

        # Separate the filename and extension
        file_root, file_ext = os.path.splitext(file.name)

        if file_root != data["name"] or file.type != lowercase_type:
            name_or_type_changed = True

        # Update the filename while keeping the original extension
        new_filename = data["name"] + file_ext

        file.name = new_filename
        file.type = lowercase_type
        file.maxDownloadSpeed = data["maxDownloadSpeed"]
        file.maxUploadSpeed = data["maxUploadSpeed"]
        file.techType = data["techType"]
        file.latency = data["latency"]
        file.category = data["category"]
        kml_entries = kml_ops.get_kml_data_by_file(file_id, session)
        for kml_entry in kml_entries:
            kml_entry.maxDownloadSpeed = data["maxDownloadSpeed"]
            kml_entry.maxUploadSpeed = data["maxUploadSpeed"]
            kml_entry.techType = data["techType"]
            kml_entry.latency = data["latency"]
            kml_entry.category = data["category"]

        session.commit()

        if name_or_type_changed:
            userVal = user_ops.get_user_with_id(identity["id"], session=session)
            result = process_data.apply_async(args=[file.folder_id, 4])
            folderVal = folder_ops.get_folder_with_id(folderid=file.folder_id, session=session)
            celerytaskinfo_ops.create_celery_taskinfo(
                task_id=result.task_id,
                status="PENDING",
                operation_type="Update",
                operation_detail="Update filename or filetype in a filing",
                user_email=userVal.email,
                organization_id=userVal.organization_id,
                folder_deadline=folderVal.deadline,
                session=session,
                files_changed=file.name,
            )
        return jsonify(
            {"status": "success", "message": "File and its KML data updated successfully"}
        ), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        session.close()


@bp.route("/api/delfiles", methods=["DELETE"])
@jwt_required()
def delete_files():
    try:
        data = request.get_json()
        file_ids = data.get("file_ids", [])
        editfile_ids = data.get("editfile_ids", [])
        identity = get_jwt_identity()

        logger.debug(file_ids)
        logger.debug(editfile_ids)

        if not file_ids and not editfile_ids:
            return jsonify({"status": "error", "message": "Please check the files to delete"}), 400

        session = Session()

        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)

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

        for fileid in file_ids:
            fileid = int(fileid)
            if not file_ops.file_belongs_to_organization(
                file_id=fileid, user_id=identity["id"], session=session
            ):
                session.close()
                return jsonify(
                    {
                        "status": "error",
                        "message": "You are accessing a filing not belong to your organization",
                    }
                ), 400

        for editfileid in editfile_ids:
            editfileid = int(editfileid)
            if not editfile_ops.editfile_belongs_to_organization(
                file_id=editfileid, user_id=identity["id"], session=session
            ):
                session.close()
                return jsonify(
                    {
                        "status": "error",
                        "message": "You are accessing a filing not belong to your organization",
                    }
                ), 400

        filenames = []
        if file_ids:
            fileVal = file_ops.get_file_with_id(fileid=file_ids[0], session=session)
            folderid = fileVal.folder_id

            for fileid in file_ids:
                fileVal = file_ops.get_file_with_id(fileid=fileid, session=session)
                filenames.append(fileVal.name)

        else:
            editfileVal = editfile_ops.get_editfile_with_id(fileid=editfile_ids[0], session=session)
            folderid = editfileVal.folder_id

            for editfileid in editfile_ids:
                fileVal = editfile_ops.get_editfile_with_id(fileid=editfileid, session=session)
                filenames.append(fileVal.name)

        folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
        deadline = folderVal.deadline
        concatenated_filenames = ", ".join(filenames)

        logger.info(f"folderid in delete files {folderid}")
        task_chain = chain(
            async_delete_files.s(file_ids=file_ids, editfile_ids=editfile_ids),
            process_data.si(folderid=folderid, operation=4),
        )
        result = task_chain.apply_async()
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Delete",
            operation_detail="Delete files in a filing",
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
    finally:
        session.close()


@bp.route("/api/download-kmlfile/<string:kml_filename>", methods=["GET"])
@jwt_required()
def download_kmlfile(kml_filename):
    session = Session()
    try:
        identity = get_jwt_identity()
        folderVal = folder_ops.get_upload_folder(
            userid=identity["id"], folderid=None, session=session
        )
        fileVal = file_ops.get_file_with_name(
            filename=kml_filename, folderid=folderVal.id, session=session
        )
        if isinstance(fileVal, str):  # In case create_tower returned an error message
            logger.debug(fileVal)
            return jsonify({"status": "error", "message": fileVal}), 400

        if not fileVal:
            return jsonify({"status": "error", "message": "File not found"}), 404

        downfile = io.BytesIO(fileVal.data)
        downfile.seek(0)
        return send_file(
            downfile, download_name=fileVal.name, as_attachment=True, mimetype="text/kml"
        )

    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    finally:
        session.close()
