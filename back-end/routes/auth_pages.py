"""Server-rendered auth pages (/auth/*) in the new shell.

Same flows and limits as the /api endpoints (which the SPA keeps using in
parallel until cutover), but as plain HTML forms styled with the civic
tokens: login, register, request-a-reset, set-a-new-password, logout. The
new app's pages 302 here when unauthenticated — a non-SPA login target,
required before cutover. Real-world accounts are operator-created; the reset
flow doubles as activation (temp password → set your own).
"""

import jwt
from flask import Blueprint, make_response, redirect, render_template, request
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)

from controllers.database_controller import setting_ops, user_ops
from database.sessions import get_session
from routes._email import (
    EMAIL_TOKEN_AUDIENCE,
    create_email_token,
    send_verification_email_with_token,
)
from services.audit import log_action
from utils.flask_app import app, limiter
from utils.passwords import needs_rehash, verify_password
from utils.validation import is_valid_email

bp = Blueprint("auth_pages", __name__, template_folder="../templates")


@bp.context_processor
def _inject_theme():
    """The site theme, so the auth card matches the rest of the app (bdk.css
    scopes every design token to body.app + the theme class)."""
    return {"site_theme": setting_ops.get_site_theme(get_session())}


def _page(template, **ctx):
    return render_template(template, **ctx)


@bp.route("/auth/login")
def login_page():
    return _page("app/auth_login.html", error=None)


@bp.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login_submit():
    email = (request.form.get("email") or "").strip()
    pword = request.form.get("password") or ""
    user = user_ops.get_user_with_email(email)
    if user is None or not verify_password(user.password, pword):
        # Don't leak whether the email exists; record the attempted email.
        log_action("login_failed", details={"email": email})
        return _page("app/auth_login.html", error="Invalid credentials")
    if needs_rehash(user.password):
        # Legacy (pre-pbkdf2) hash: the user just proved the password, so
        # upgrade the stored hash in place — no forced reset.
        user_ops.reset_user_password(user.id, pword)
    if getattr(user, "disabled", False):
        log_action("login_disabled", user_id=user.id, resource_type="user", resource_id=user.id)
        return _page("app/auth_login.html", error="This account has been disabled.")
    access_token = create_access_token(identity={"id": user.id})
    response = make_response(redirect(request.args.get("next") or "/map"))
    set_access_cookies(response, access_token)
    log_action("login", user_id=user.id, resource_type="user", resource_id=user.id)
    return response


@bp.route("/auth/register")
def register_page():
    return _page("app/auth_register.html", error=None)


@bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per minute")
def register_submit():
    session = get_session()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    if not is_valid_email(email):
        return _page("app/auth_register.html", error="Please provide a valid email address.")
    if not password:
        return _page("app/auth_register.html", error="Please provide a password.")
    result = user_ops.create_user_in_db(email, password, session)
    if "error" in result:
        return _page("app/auth_register.html", error=result["error"])
    userVal = result["success"]
    _send_verify_email(userVal)
    access_token = create_access_token(identity={"id": userVal.id})
    # Straight into the funnel: the setup page (org first, then the doors).
    # The header wears a verify-your-email banner until the link is clicked.
    response = make_response(redirect("/setup"))
    set_access_cookies(response, access_token)
    return response


def _send_verify_email(userVal):
    """Best-effort: registration must never fail because the mailer is down —
    the header banner's resend button covers a missed send."""
    try:
        token = create_email_token(
            userid=userVal.id, email=userVal.email, operation="email_address_verification"
        )
        send_verification_email_with_token(
            email=userVal.email,
            token=token,
            title="Verify Your Email Address for BDK",
            content="verify your email address",
            link_path=f"/auth/verify/{token}",
        )
    except Exception:
        from utils.logger_config import logger

        logger.exception("verification email failed to send")


@bp.route("/auth/verify/<token>")
def verify_email(token):
    """The emailed verification link: verifies and sends the user onward."""
    session = get_session()
    try:
        decoded = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            audience=EMAIL_TOKEN_AUDIENCE,
            options={"verify_sub": False},
        )
        if decoded["sub"]["operation"] != "email_address_verification":
            raise ValueError
        if not user_ops.verify_user_email(
            decoded["sub"]["id"], decoded["sub"]["email"], session, True
        ):
            raise ValueError
    except jwt.ExpiredSignatureError:
        return _page(
            "app/auth_verified.html", ok=False, error="That link has expired — request a new one."
        )
    except Exception:
        return _page("app/auth_verified.html", ok=False, error="That link is not valid.")
    return _page("app/auth_verified.html", ok=True, error=None)


@bp.route("/auth/verify/resend", methods=["POST"])
@limiter.limit("5 per minute")
def verify_resend():
    """The header banner's resend button (needs a logged-in session)."""
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    session = get_session()
    try:
        verify_jwt_in_request()
        identity = get_jwt_identity()
    except Exception:
        return redirect("/auth/login")
    userVal = user_ops.get_user_with_id(identity["id"], session=session)
    if userVal is not None and not userVal.verified:
        _send_verify_email(userVal)
    return redirect(request.referrer or "/setup")


@bp.route("/auth/reset")
def reset_request_page():
    return _page("app/auth_reset.html", error=None, sent=False)


@bp.route("/auth/reset", methods=["POST"])
@limiter.limit("5 per minute")
def reset_request_submit():
    session = get_session()
    email = (request.form.get("email") or "").strip()
    user = user_ops.get_user_with_email(email, session)
    if user is not None:
        token = create_email_token(userid=user.id, email=user.email, operation="reset_password")
        send_verification_email_with_token(
            email=email,
            token=token,
            title="Reset Your Password for BDK",
            content="reset your password",
            link_path=f"/auth/reset/{token}",
        )
    # Same response either way — never reveal whether the email exists.
    return _page("app/auth_reset.html", error=None, sent=True)


@bp.route("/auth/reset/<token>")
def reset_token_page(token):
    return _page("app/auth_reset_token.html", token=token, error=None)


@bp.route("/auth/reset/<token>", methods=["POST"])
@limiter.limit("10 per minute")
def reset_token_submit(token):
    session = get_session()
    new_password = request.form.get("password") or ""
    if not new_password:
        return _page("app/auth_reset_token.html", token=token, error="Please enter a password.")
    try:
        decoded = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            audience=EMAIL_TOKEN_AUDIENCE,
            options={"verify_sub": False},
        )
        user_id = decoded["sub"]["id"]
        email = decoded["sub"]["email"]
        if not user_ops.verify_user_email(user_id, email, session, False):
            raise ValueError
        user_ops.reset_user_password(user_id, new_password)
    except jwt.ExpiredSignatureError:
        return _page(
            "app/auth_reset_token.html",
            token=token,
            error="That link has expired — request a new one.",
        )
    except Exception:
        return _page(
            "app/auth_reset_token.html",
            token=token,
            error="That link is not valid — request a new one.",
        )
    return redirect("/auth/login")


@bp.route("/auth/logout", methods=["POST"])
def logout_submit():
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        user_id = identity.get("id") if identity else None
    except Exception:
        user_id = None
    log_action("logout", user_id=user_id)
    response = make_response(redirect("/auth/login"))
    unset_jwt_cookies(response)
    return response
