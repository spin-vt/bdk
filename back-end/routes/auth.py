"""Authentication: register, login, logout, password reset, email verification."""

import jwt
from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import create_access_token
from jwt import ExpiredSignatureError
from werkzeug.security import check_password_hash

from controllers.database_controller import (
    user_ops,
)
from database.sessions import Session
from routes._email import create_email_token, send_verification_email_with_token
from utils.flask_app import app
from utils.logger_config import logger
from utils.settings import IN_PRODUCTION

bp = Blueprint("auth", __name__)


@bp.route("/api/request_password_reset", methods=["POST"])
def request_password_reset():
    session = Session()
    data = request.get_json()
    email = data.get("email")
    user = user_ops.get_user_with_email(email, session)

    if not user:
        session.close()
        return jsonify({"status": "error", "message": "Email address not found."}), 400

    email_token = create_email_token(userid=user.id, email=user.email, operation="reset_password")
    send_verification_email_with_token(
        email=email,
        token=email_token,
        title="Reset Your Password for BDK",
        content="reset your password",
    )
    session.close()
    return jsonify({"status": "success", "message": "Verification email resent."}), 200


@bp.route("/api/reset_password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("newPassword")

    try:
        session = Session()
        decoded_token = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        user_id = decoded_token["sub"]["id"]
        email = decoded_token["sub"]["email"]
        if user_ops.verify_user_email(user_id, email, session, False):
            user_ops.reset_user_password(user_id, new_password)
            return jsonify({"status": "success", "message": "Password reset successfully."}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid token."}), 400
    except jwt.ExpiredSignatureError:
        return jsonify({"status": "error", "message": "The token has expired."}), 400
    except Exception:
        return jsonify({"status": "error", "message": "Invalid token."}), 400
    finally:
        session.close()


@bp.route("/api/verify_token", methods=["POST"])
def verify_token():
    try:
        session = Session()
        data = request.get_json()
        token = data.get("token")

        # Decode the token using pyjwt directly
        decoded_token = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])

        user_id = decoded_token["sub"]["id"]
        email = decoded_token["sub"]["email"]
        operation = decoded_token["sub"]["operation"]

        logger.debug(operation)

        setVerified = True if operation == "email_address_verification" else False
        if user_ops.verify_user_email(user_id, email, session, setVerified):
            if operation == "join_organization":
                org_id = int(decoded_token["sub"]["org_id"])
                logger.debug(org_id)
                if org_id < 0:
                    return jsonify({"status": "error", "message": "Invalid organization id."}), 400
                user_ops.add_user_to_organization(user_id, org_id, session)

            response = make_response(jsonify({"status": "success"}))

            return response, 200
        else:
            return jsonify({"status": "error", "message": "Invalid token."}), 400
    except ExpiredSignatureError:
        return jsonify({"status": "error", "message": "The token has expired."}), 400
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return jsonify({"status": "error", "message": "Invalid token."}), 400
    finally:
        session.close()


@bp.route("/api/send_email_verification", methods=["POST"])
def send_email_verification():
    session = Session()
    data = request.get_json()
    email = data.get("email")
    user = user_ops.get_user_with_email(email, session)

    if not user:
        session.close()
        return jsonify({"status": "error", "message": "Email address not found."}), 400

    email_token = create_email_token(
        userid=user.id, email=user.email, operation="email_address_verification"
    )
    send_verification_email_with_token(
        email=email,
        token=email_token,
        title="Verify Your Email Address for BDK",
        content="verify your email address",
    )
    session.close()
    return jsonify({"status": "success", "message": "Verification email sent."}), 200


@bp.route("/api/register", methods=["POST"])
def register():
    session = Session()
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    response = user_ops.create_user_in_db(email, password, session)

    if "error" in response:
        return jsonify({"status": "error", "message": response["error"]}), 400

    userVal = response["success"]
    access_token = create_access_token(identity={"id": userVal.id})

    response = make_response(jsonify({"status": "success"}))
    if IN_PRODUCTION:
        response.set_cookie("token", access_token, httponly=True, samesite="Lax", secure=True)
    else:
        response.set_cookie("token", access_token, httponly=False, samesite="Lax", secure=False)

    session.close()
    return response, 200


@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    pword = data.get("password")

    # Needs a try catch to return the correct message
    user = user_ops.get_user_with_email(email)

    if user is not None and check_password_hash(user.password, pword):
        user_id = user.id
        access_token = create_access_token(identity={"id": user_id})
        response = make_response(jsonify({"status": "success"}))
        if IN_PRODUCTION:
            response.set_cookie("token", access_token, httponly=True, samesite="Lax", secure=True)
        else:
            response.set_cookie("token", access_token, httponly=False, samesite="Lax", secure=False)
        return response
    else:
        return jsonify({"status": "error", "message": "Invalid credentials"})


@bp.route("/api/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"status": "success", "message": "Logged out"}))
    response.delete_cookie("token")
    return response
