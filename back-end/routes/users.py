"""User profile endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from controllers.database_controller import (
    user_ops,
)
from database.sessions import Session

bp = Blueprint("users", __name__)


@bp.route("/api/user", methods=["GET"])
@jwt_required()
def get_user_info():
    session = Session()
    try:
        identity = get_jwt_identity()

        userVal = user_ops.get_user_with_id(identity["id"], session=session)
        if not userVal:
            return jsonify({"status": "error", "message": "Please login to your account"}), 401
        userinfo = user_ops.get_userinfo_with_id(identity["id"], session=session)
        return jsonify({"status": "success", "userinfo": userinfo}), 200
    except NoAuthorizationError:
        return jsonify({"status": "error", "message": "Please login to your account"}), 401
    finally:
        session.close()


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

        session = Session()
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
    finally:
        session.close()
