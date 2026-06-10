"""User profile endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.database_controller import (
    user_ops,
)
from database.sessions import get_session
from utils.logger_config import logger
from utils.validation import is_valid_email

bp = Blueprint("users", __name__)


@bp.route("/api/user", methods=["GET"])
@jwt_required()
def get_user_info():
    session = get_session()
    try:
        identity = get_jwt_identity()

        userVal = user_ops.get_user_with_id(identity["id"], session=session)
        if not userVal:
            return jsonify({"status": "error", "message": "Please login to your account"}), 401
        userinfo = user_ops.get_userinfo_with_id(identity["id"], session=session)
        # Impersonation banner: when a platform admin is "logged in as" this user,
        # the app token carries an `impersonator` claim. Surface the operator's
        # email so the SPA can show the banner + "Return to admin" link.
        impersonator_id = identity.get("impersonator") if isinstance(identity, dict) else None
        if impersonator_id and isinstance(userinfo, dict):
            operator = user_ops.get_user_with_id(impersonator_id, session=session)
            userinfo["impersonator"] = (
                operator.email if operator and not isinstance(operator, str) else True
            )
        return jsonify({"status": "success", "userinfo": userinfo}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401


@bp.route("/api/update_profile", methods=["POST"])
@jwt_required()
def update_profile():
    session = get_session()
    try:
        identity = get_jwt_identity()
        # Only fields actually present in the body are applied — a missing
        # field must never coerce to the string "None" (str(None)) and
        # overwrite real data, which the old code did.
        data = request.get_json(silent=True) or {}
        provider_id = data.get("providerId")
        brand_name = data.get("brandName")
        email = data.get("email")
        org_name = data.get("organizationName")

        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)

        if email and email != userVal.email:
            if not is_valid_email(email):
                return jsonify(
                    {"status": "error", "message": "Please provide a valid email address."}
                ), 400
            if user_ops.get_user_with_email(email, session):
                return jsonify(
                    {"status": "error", "message": "That email address is already in use."}
                ), 400
            userVal.email = email
            userVal.verified = False

        organization = userVal.organization
        if organization:
            if provider_id:
                organization.provider_id = provider_id
            if brand_name:
                organization.brand_name = str(brand_name)
            if org_name:
                organization.name = str(org_name)
        session.commit()
        return jsonify({"status": "success", "message": "User profile updated successfully."}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception:
        # Log the detail server-side; never echo internals to the client.
        logger.exception("update_profile failed")
        session.rollback()
        return jsonify({"status": "error", "message": "Failed to update profile."}), 500
