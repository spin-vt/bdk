"""Platform-admin authentication & authorization.

The admin panel runs on a SEPARATE session from the main app:

* The app authenticates the SPA with a flask-jwt-extended access cookie named
  ``token`` (dict identity ``{"id": ...}``). flask-jwt-extended supports exactly
  one access cookie + identity scheme, so the admin session cannot reuse it
  without letting admin tokens reach app routes (privilege confusion).
* The admin session is therefore its own JWT in an ``admin_session`` cookie,
  signed with the same ``JWT_SECRET_KEY`` but decoded MANUALLY with PyJWT (the
  same idiom routes/auth.py already uses for email/reset tokens). It carries a
  ``typ=admin`` discriminator and a per-session ``csrf`` secret.

``require_platform_admin`` re-reads the user from the DB on every request and
re-checks ``is_platform_admin and not disabled``, so revoking the flag in the DB
takes effect immediately despite the token being stateless.

Impersonation ("login as") mints an *app* ``token`` for the target user and is
implemented in the admin service/routes — it deliberately never touches
``admin_session``, so the operator stays logged into the panel.
"""

import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, redirect, request

from controllers.database_controller import user_ops
from database.sessions import get_session

ADMIN_COOKIE = "admin_session"
ADMIN_API_PREFIX = "/admin/api"
ADMIN_LOGIN_PATH = "/admin/login"
ADMIN_SESSION_HOURS = 2
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def mint_admin_session(user_id, ttl_hours=ADMIN_SESSION_HOURS):
    """Mint an admin-session JWT for a platform admin. Returns (token, csrf).

    The csrf secret is embedded in the signed, httponly cookie; admin pages echo
    it and htmx sends it back as X-CSRF-Token, giving stateless double-submit
    CSRF protection without a CSRF library.
    """
    now = datetime.now(UTC)
    csrf = secrets.token_hex(16)
    token = jwt.encode(
        {
            "typ": "admin",
            "sub": {"id": user_id},
            "csrf": csrf,
            "iat": now,
            "exp": now + timedelta(hours=ttl_hours),
        },
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return token, csrf


def decode_admin_session(token):
    """Decode + verify an admin-session JWT. Returns the payload or None."""
    if not token:
        return None
    try:
        # verify_sub=False: we follow the app's dict-identity convention
        # (sub={"id": ...}), but PyJWT >= 2.10 enforces RFC 7519's "sub must be a
        # string" by default — the same reason the app sets JWT_VERIFY_SUB=False.
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_sub": False},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "admin":
        return None
    return payload


def _is_api_request():
    return request.path.startswith(ADMIN_API_PREFIX)


def _reject_unauthenticated():
    """No/invalid admin session: 401 for the API, redirect to login for the UI."""
    if _is_api_request():
        return jsonify({"status": "error", "message": "Admin authentication required"}), 401
    return redirect(ADMIN_LOGIN_PATH)


def _reject_forbidden(message="Forbidden"):
    if _is_api_request():
        return jsonify({"status": "error", "message": message}), 403
    # A logged-out-looking UI redirect is wrong here (the user IS authenticated
    # but not authorized); a bare 403 is clearer.
    return message, 403


def require_platform_admin(fn):
    """Guard every admin UI + admin API route. Validates the admin_session
    cookie, re-checks platform-admin status against the DB, and enforces CSRF on
    unsafe methods. Stashes the operator on ``g.admin_user``."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        payload = decode_admin_session(request.cookies.get(ADMIN_COOKIE))
        if not payload:
            return _reject_unauthenticated()

        user_id = (payload.get("sub") or {}).get("id")
        session = get_session()
        operator = user_ops.get_user_with_id(user_id, session)
        # get_user_with_id returns None (missing) or a str (DB error) on failure.
        if not operator or isinstance(operator, str):
            return _reject_forbidden("Account not found")
        if not getattr(operator, "is_platform_admin", False) or getattr(
            operator, "disabled", False
        ):
            return _reject_forbidden("Platform admin privileges required")

        if request.method in _UNSAFE_METHODS:
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            expected = payload.get("csrf") or ""
            if not sent or not secrets.compare_digest(sent, expected):
                return _reject_forbidden("Invalid or missing CSRF token")

        g.admin_user = operator
        g.admin_csrf = payload.get("csrf")
        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    """Org-level guard for existing app (`/api/*`) routes that should be limited
    to an organization admin (``user.is_admin``). Self-contained: verifies the
    app JWT itself, so it does not need to be stacked under @jwt_required."""
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        identity = get_jwt_identity()
        session = get_session()
        current = user_ops.get_user_with_id(identity["id"], session)
        if not current or isinstance(current, str):
            return jsonify({"status": "error", "message": "Account not found"}), 403
        if getattr(current, "disabled", False) or not getattr(current, "is_admin", False):
            return jsonify({"status": "error", "message": "Admin privileges required"}), 403
        g.current_user = current
        return fn(*args, **kwargs)

    return wrapper
