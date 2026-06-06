"""Export workflow: export a filing, list/download/delete exports."""

import io

from flask import Blueprint, jsonify, make_response, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    async_folder_delete,
)
from controllers.database_controller import (
    celerytaskinfo_ops,
    file_ops,
    folder_ops,
    kml_ops,
    user_ops,
)
from database.sessions import Session
from utils.namingschemes import (
    DATE_FORMAT,
    EXPORT_CSV_NAME_TEMPLATE,
)

bp = Blueprint("export", __name__)


@bp.route("/api/exportFiling/<folderid>", methods=["GET"])
@jwt_required()
def exportFiling(folderid):
    try:
        identity = get_jwt_identity()
        folderid = int(folderid)
        session = Session()
        try:
            if folderid == -1:
                return jsonify({"status": "error", "message": "Invalid filing requested"}), 400

            if not folder_ops.folder_belongs_to_organization(folderid, identity["id"], session):
                return jsonify(
                    {
                        "status": "error",
                        "message": "You are accessing a filing not belong to your organization",
                    }
                ), 400

            folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
            providerid = folderVal.organization.provider_id
            brandname = folderVal.organization.brand_name
            deadline = folderVal.deadline.strftime(DATE_FORMAT)

            if not providerid or not brandname:
                return jsonify(
                    {"status": "error", "message": "Please provide your provider ID and brand name"}
                ), 400

            csv_output = kml_ops.export(folderid, providerid, brandname, deadline, session)

            if csv_output:
                download_name = EXPORT_CSV_NAME_TEMPLATE.format(
                    brand_name=brandname, deadline=deadline
                )

                csv_output.seek(0)
                response = make_response(
                    send_file(
                        csv_output,
                        as_attachment=True,
                        download_name=download_name,
                        mimetype="text/csv",
                    )
                )
                response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
                return response
            else:
                return jsonify({"status": "error", "message": "internal server error"})
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/export", methods=["GET"])
@jwt_required()
def get_exported_folders():
    try:
        identity = get_jwt_identity()
        session = Session()
        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)
        folders = folder_ops.get_folders_by_type_for_org(
            orgid=userVal.organization_id, foldertype="export", session=session
        )

        response_data = []
        for fldr in folders:
            exportcsv_in_folder = file_ops.get_files_by_type(
                folderid=fldr.id, filetype="export", session=session
            )
            # exportcsv_in_folder = file_ops.get_files_in_folder(folderid=fldr.id, session=session)

            # print(exportcsv_in_folder)
            for f in exportcsv_in_folder:
                file_data = {
                    "id": f.id,
                    "name": f.name,
                    "timestamp": f.timestamp,
                    "type": f.type,
                    "folder_id": f.folder_id,
                }
                response_data.append(file_data)

        return jsonify(response_data), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        session.close()


@bp.route("/api/delexport/<int:fileid>", methods=["DELETE"])
@jwt_required()
def delete_export(fileid):
    fileid = int(fileid)
    session = Session()
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
        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)

        folderVal = folder_ops.get_folder_with_id(fileVal.folder_id, session=session)
        deadline = folderVal.deadline
        result = async_folder_delete.apply_async(args=[fileVal.folder_id])
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Delete",
            operation_detail="Delete a filing export snapshot",
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=deadline,
            session=session,
        )
        return jsonify({"status": "success"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    finally:
        session.close()


@bp.route("/api/downloadexport/<int:fileid>", methods=["GET"])
@jwt_required()
def download_export(fileid):
    fileid = int(fileid)
    session = Session()
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
    finally:
        session.close()
