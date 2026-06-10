"""Authentication: register, login, logout, password reset, email verification."""

import jwt
from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from jwt import ExpiredSignatureError
from werkzeug.security import check_password_hash

from controllers.database_controller import (
    user_ops,
)
from database.sessions import get_session
from routes._email import (
    EMAIL_TOKEN_AUDIENCE,
    create_email_token,
    send_verification_email_with_token,
)
from services.audit import log_action
from utils.flask_app import app, limiter
from utils.logger_config import logger
from utils.validation import is_valid_email

bp = Blueprint("auth", __name__)


@bp.route("/api/request_password_reset", methods=["POST"])
@limiter.limit("5 per minute")
def request_password_reset():
    session = get_session()
    data = request.get_json()
    email = data.get("email")
    user = user_ops.get_user_with_email(email, session)

    if not user:
        return jsonify({"status": "error", "message": "Email address not found."}), 400

    email_token = create_email_token(userid=user.id, email=user.email, operation="reset_password")
    send_verification_email_with_token(
        email=email,
        token=email_token,
        title="Reset Your Password for BDK",
        content="reset your password",
    )
    return jsonify({"status": "success", "message": "Verification email resent."}), 200


@bp.route("/api/reset_password", methods=["POST"])
@limiter.limit("10 per minute")
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("newPassword")

    try:
        session = get_session()
        decoded_token = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            audience=EMAIL_TOKEN_AUDIENCE,
            options={"verify_sub": False},
        )
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


@bp.route("/api/verify_token", methods=["POST"])
def verify_token():
    try:
        session = get_session()
        data = request.get_json()
        token = data.get("token")

        # Decode the token using pyjwt directly. verify_sub=False because these
        # email tokens carry a dict `sub` ({"id", "email", "operation", ...}),
        # which PyJWT >= 2.10 rejects by default (RFC 7519 "sub must be a
        # string") — same reason the app sets JWT_VERIFY_SUB=False. The
        # audience requirement rejects any non-email token (e.g. a session JWT
        # signed with the same key).
        decoded_token = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            audience=EMAIL_TOKEN_AUDIENCE,
            options={"verify_sub": False},
        )

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


@bp.route("/api/send_email_verification", methods=["POST"])
@limiter.limit("5 per minute")
def send_email_verification():
    session = get_session()
    data = request.get_json()
    email = data.get("email")
    user = user_ops.get_user_with_email(email, session)

    if not user:
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
    return jsonify({"status": "success", "message": "Verification email sent."}), 200


@bp.route("/api/register", methods=["POST"])
@limiter.limit("10 per minute")
def register():
    session = get_session()
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not is_valid_email(email):
        return jsonify({"status": "error", "message": "Please provide a valid email address."}), 400
    if not password:
        return jsonify({"status": "error", "message": "Please provide a password."}), 400

    response = user_ops.create_user_in_db(email, password, session)

    if "error" in response:
        return jsonify({"status": "error", "message": response["error"]}), 400

    userVal = response["success"]
    access_token = create_access_token(identity={"id": userVal.id})

    response = make_response(jsonify({"status": "success"}))
    # Sets the HttpOnly `token` cookie plus the JS-readable csrf_access_token
    # (flags from JWT_COOKIE_* config: Secure in prod, SameSite=Lax).
    set_access_cookies(response, access_token)

    return response, 200


@bp.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()
    email = data.get("email")
    pword = data.get("password")

    # Needs a try catch to return the correct message
    user = user_ops.get_user_with_email(email)

    if user is not None and check_password_hash(user.password, pword):
        # A soft-disabled account cannot obtain a fresh session. Checked
        # only after the password verifies, so we never reveal disabled status
        # to someone who doesn't already hold the credentials.
        if getattr(user, "disabled", False):
            log_action("login_disabled", user_id=user.id, resource_type="user", resource_id=user.id)
            return jsonify({"status": "error", "message": "This account has been disabled."}), 403
        user_id = user.id
        access_token = create_access_token(identity={"id": user_id})
        response = make_response(jsonify({"status": "success"}))
        set_access_cookies(response, access_token)
        log_action("login", user_id=user_id, resource_type="user", resource_id=user_id)
        return response
    else:
        # Don't leak whether the email exists; record the attempted email.
        log_action("login_failed", details={"email": email})
        return jsonify({"status": "error", "message": "Invalid credentials"})


@bp.route("/api/logout", methods=["POST"])
def logout():
    # Logout isn't @jwt_required; best-effort identify the actor for the audit
    # trail without failing if the cookie is missing/expired.
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        user_id = identity.get("id") if identity else None
    except Exception:
        user_id = None
    log_action("logout", user_id=user_id)
    response = make_response(jsonify({"status": "success", "message": "Logged out"}))
    unset_jwt_cookies(response)  # clears the token AND csrf cookies
    return response
