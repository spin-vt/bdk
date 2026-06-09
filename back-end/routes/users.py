"""User profile endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.database_controller import (
    user_ops,
)
from database.sessions import get_session

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
    try:
        identity = get_jwt_identity()
        data = request.get_json()
        provider_id = data.get("providerId")
        brand_name = str(data.get("brandName"))
        email = str(data.get("email"))
        org_name = str(data.get("organizationName"))

        session = get_session()
        userVal = user_ops.get_user_with_id(userid=identity["id"], session=session)

        if email and email != userVal.email:
            userVal.email = email
            userVal.verified = False

        organization = userVal.organization
        if organization:
            if provider_id:
                organization.provider_id = provider_id
            if brand_name:
                organization.brand_name = brand_name
            if org_name:
                organization.name = org_name
        session.commit()
        return jsonify({"status": "success", "message": "User profile updated successfully."}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    except Exception as e:
        session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
