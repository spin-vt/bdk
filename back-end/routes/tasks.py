"""Celery task status endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from controllers.database_controller import (
    celerytaskinfo_ops,
    user_ops,
)
from database.sessions import get_session

bp = Blueprint("tasks", __name__)


@bp.route("/api/user-tasks", methods=["GET"])
@jwt_required()
def get_user_tasks():
    session = get_session()
    try:
        identity = get_jwt_identity()

        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)
        if not userVal:
            return jsonify({"status": "error", "message": "User not found"}), 400
        if not userVal.organization:
            return jsonify(
                {"status": "error", "message": "User not associated with organization"}
            ), 400

        in_progress_tasks, finished_tasks = celerytaskinfo_ops.get_celerytasksinfo_for_org(
            orgid=userVal.organization_id, session=session
        )

        return jsonify(
            {
                "status": "success",
                "in_progress_tasks": in_progress_tasks,
                "finished_tasks": finished_tasks,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api/estimated-task-runtime/<taskid>", methods=["GET"])
@jwt_required()
def get_estimated_task_runtime(taskid):
    session = get_session()
    try:
        identity = get_jwt_identity()
        taskid = str(taskid)
        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)
        if not userVal:
            return jsonify({"status": "error", "message": "User not found"}), 400
        if not userVal.organization:
            return jsonify(
                {"status": "error", "message": "User not associated with organization"}
            ), 400
        if not celerytaskinfo_ops.task_belongs_to_organization(
            task_id=taskid, user_id=userVal.id, session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a task not belong to your organization",
                }
            ), 400

        estimated_runtime_seconds = celerytaskinfo_ops.get_estimated_runtime_for_task(
            task_id=taskid, session=session
        )

        return jsonify({"status": "success", "estimated_runtime": estimated_runtime_seconds}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/api/update-task-status/<taskid>", methods=["POST"])
@jwt_required()
def update_task_status(taskid):
    session = get_session()
    try:
        identity = get_jwt_identity()
        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)
        taskid = str(taskid)
        if not userVal:
            return jsonify({"status": "error", "message": "User not found"}), 400

        if not userVal.organization:
            return jsonify(
                {"status": "error", "message": "User not associated with organization"}
            ), 400

        if not celerytaskinfo_ops.task_belongs_to_organization(
            task_id=taskid, user_id=userVal.id, session=session
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "You are accessing a task not belonging to your organization",
                }
            ), 400

        # Get the new status from the request body
        data = request.get_json()
        new_status = data.get("status")

        if not new_status:
            return jsonify({"status": "error", "message": "Status is required"}), 400

        # Update the task status
        celerytaskinfo_ops.update_task_status(task_id=taskid, status=new_status, session=session)

        return jsonify({"status": "success", "message": "Task status updated successfully"}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
