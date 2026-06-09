"""Organization create/join/delete/exit."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.celery_controller.celery_tasks import (
    async_org_delete,
)
from controllers.database_controller import (
    organization_ops,
    user_ops,
)
from database.sessions import get_session
from routes._email import create_email_token, send_verification_email_with_token
from services.audit import log_action
from utils.admin_auth import require_admin
from utils.logger_config import logger

bp = Blueprint("organizations", __name__)


@bp.route("/api/create_organization", methods=["POST"])
@jwt_required()
def create_organization():
    try:
        current_user = get_jwt_identity()
        session = get_session()
        data = request.get_json()
        org_name = data.get("orgName")
        user = user_ops.get_user_with_id(current_user["id"], session)

        if not user.verified:
            return jsonify(
                {
                    "status": "error",
                    "message": "Please verify your email address before creating an organization.",
                }
            ), 400

        if not org_name:
            return jsonify(
                {"status": "error", "message": "Please enter an organization name."}
            ), 400

        existing_org = organization_ops.get_organization_with_orgname(
            org_name=org_name, session=session
        )
        if existing_org:
            return jsonify({"status": "error", "message": "Organization name already exists."}), 400

        new_org = organization_ops.create_organization(org_name=org_name, session=session)

        user.organization_id = new_org.id
        user.is_admin = True
        session.commit()

        log_action(
            "org_create",
            user_id=user.id,
            resource_type="organization",
            resource_id=new_org.id,
            details={"name": org_name},
        )
        return jsonify({"status": "success", "message": "Organization created successfully!"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        logger.error(f"Error creating organization: {e}")
        session.rollback()
        return jsonify(
            {"status": "error", "message": "An error occurred while creating the organization."}
        ), 500


@bp.route("/api/join_organization", methods=["POST"])
@jwt_required()
def join_organization():
    try:
        current_user = get_jwt_identity()

        session = get_session()
        data = request.get_json()
        org_name = data.get("name")
        user = user_ops.get_user_with_id(current_user["id"], session)

        if not user.verified:
            return jsonify(
                {
                    "status": "error",
                    "message": "Please verify your email address before joining an organization.",
                }
            ), 400

        if not org_name:
            return jsonify(
                {"status": "error", "message": "Please enter an organization name."}
            ), 400

        org = organization_ops.get_organization_with_orgname(org_name=org_name, session=session)
        if not org:
            return jsonify({"status": "error", "message": "Organization not found."}), 400

        admin = organization_ops.get_admin_user_for_organization(org_id=org.id, session=session)
        if not admin:
            return jsonify({"status": "error", "message": "Organization admin not found."}), 400

        email_token = create_email_token(
            userid=user.id, email=user.email, operation="join_organization", org_id=org.id
        )
        send_verification_email_with_token(
            email=admin.email,
            token=email_token,
            title="Organization Join Request for BDK",
            content="finish their organization join request",
            join_org=True,
            joining_email=user.email,
        )

        return jsonify(
            {"status": "success", "message": "Join request sent to organization admin."}
        ), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        logger.error(f"Error joining organization: {e}")
        session.rollback()
        return jsonify(
            {
                "status": "error",
                "message": "An error occurred while trying to join the organization.",
            }
        ), 500


@bp.route("/api/delete_organization", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_organization():
    try:
        identity = get_jwt_identity()
        session = get_session()
        data = request.get_json()
        orgName = data.get("organizationName")

        userVal = user_ops.get_user_with_id(identity["id"], session=session)
        organization = userVal.organization

        if not organization:
            return jsonify({"status": "error", "message": "Organization not found"}), 400

        if not organization.name == orgName:
            return jsonify({"status": "error", "message": "Organization not found"}), 400

        org_id = userVal.organization_id
        result = async_org_delete.apply_async(args=[org_id])

        log_action(
            "org_delete",
            user_id=userVal.id,
            resource_type="organization",
            resource_id=org_id,
            details={"name": orgName, "actor_email": userVal.email},
        )
        return jsonify({"status": "success", "message": "Organization deleted successfully"}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/exit_organization", methods=["POST"])
@jwt_required()
def exit_organization():
    try:
        identity = get_jwt_identity()
        session = get_session()

        user = user_ops.get_user_with_id(userid=identity["id"], session=session)
        data = request.get_json()
        orgName = data.get("organizationName")

        logger.debug(orgName)

        userVal = user_ops.get_user_with_id(identity["id"], session=session)
        organization = userVal.organization

        if not organization:
            return jsonify({"status": "error", "message": "Organization not found"}), 400

        if not organization.name == orgName:
            return jsonify({"status": "error", "message": "Organization not found"}), 400

        user.organization_id = None
        session.commit()

        return jsonify({"status": "success", "message": "Exited organization successfully"}), 200

    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
