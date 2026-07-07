"""Coverage/edit/network files: list, update, delete, download."""

from celery import chain
from flask import Blueprint, jsonify, request
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
    user_ops,
)
from database.sessions import get_session
from utils.logger_config import logger

bp = Blueprint("files", __name__)


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

        session = get_session()

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
