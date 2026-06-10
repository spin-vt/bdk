"""Admin API — platform-admin-only actions under /admin/api/*.

All routes are guarded by require_platform_admin (validates the admin_session
cookie, re-checks platform-admin status, enforces CSRF on unsafe methods) and
audited. Impersonation mints the app `token` cookie for the target user without
touching admin_session, so the operator stays logged into the panel.

These return JSON; the server-rendered UI drives them with htmx and
reacts to HX-Redirect / HX-Refresh headers.
"""

from flask import Blueprint, g, jsonify, redirect, request
from flask_jwt_extended import set_access_cookies, unset_jwt_cookies

from database.sessions import get_session
from services import admin_service
from services.audit import log_action
from services.exceptions import ServiceError
from utils.admin_auth import ADMIN_COOKIE, require_platform_admin

bp = Blueprint("admin_api", __name__)


def _set_app_token_cookie(response, token):
    """Set the SPA's `token` + csrf cookies the same way routes/auth.py does."""
    set_access_cookies(response, token)
    return response


def _body():
    """Accept either JSON or form data (htmx posts forms)."""
    return request.get_json(silent=True) or request.form


def _err(e: ServiceError):
    return jsonify({"status": "error", "message": e.message}), e.status


# --- impersonation ----------------------------------------------------------


@bp.route("/admin/api/users/<int:user_id>/impersonate", methods=["POST"])
@require_platform_admin
def impersonate(user_id):
    session = get_session()
    operator = g.admin_user
    try:
        token, target = admin_service.mint_impersonation_token(user_id, operator.id, session)
    except ServiceError as e:
        return _err(e)
    log_action(
        "impersonate_start",
        user_id=operator.id,
        resource_type="user",
        resource_id=target.id,
        details={"operator_email": operator.email, "target_email": target.email},
    )
    response = jsonify({"status": "success", "redirect": "/"})
    _set_app_token_cookie(response, token)
    # Tell htmx to navigate the browser to the SPA as the impersonated user.
    response.headers["HX-Redirect"] = "/"
    return response


@bp.route("/admin/api/impersonate/stop", methods=["GET"])
@require_platform_admin
def stop_impersonation():
    """End impersonation: clear the app token, keep admin_session. GET so the
    SPA's "Return to admin" banner link works without an admin CSRF token (the
    operator is identified by the admin_session cookie, which is required)."""
    log_action("impersonate_end", user_id=g.admin_user.id)
    response = redirect("/admin/")
    unset_jwt_cookies(response)  # clears the app token AND its csrf cookie
    return response


# --- user mutations ---------------------------------------------------------


@bp.route("/admin/api/users/<int:user_id>/reset-password", methods=["POST"])
@require_platform_admin
def reset_password(user_id):
    session = get_session()
    mode = (_body().get("mode") or "temp").lower()
    operator = g.admin_user
    try:
        if mode == "email":
            target = admin_service.send_password_reset_email(user_id, session)
            log_action(
                "password_reset_email",
                user_id=operator.id,
                resource_type="user",
                resource_id=target.id,
                details={"target_email": target.email},
            )
            return jsonify({"status": "success", "message": f"Reset email sent to {target.email}."})
        else:
            temp_password, target = admin_service.reset_password_temp(user_id, session)
            # NOTE: the plaintext is returned to the operator but NEVER written to
            # the audit log.
            log_action(
                "password_reset_temp",
                user_id=operator.id,
                resource_type="user",
                resource_id=target.id,
                details={"target_email": target.email},
            )
            return jsonify(
                {
                    "status": "success",
                    "message": f"Temporary password set for {target.email}.",
                    "temp_password": temp_password,
                }
            )
    except ServiceError as e:
        return _err(e)


@bp.route("/admin/api/users/<int:user_id>/verified", methods=["POST"])
@require_platform_admin
def set_verified(user_id):
    session = get_session()
    value = _truthy(_body().get("value"))
    try:
        target = admin_service.set_verified(user_id, value, session)
    except ServiceError as e:
        return _err(e)
    log_action(
        "set_verified",
        user_id=g.admin_user.id,
        resource_type="user",
        resource_id=target.id,
        details={"value": value, "target_email": target.email},
    )
    return _ok_refresh(f"{target.email} verified set to {value}.")


@bp.route("/admin/api/users/<int:user_id>/disabled", methods=["POST"])
@require_platform_admin
def set_disabled(user_id):
    session = get_session()
    value = _truthy(_body().get("value"))
    try:
        target = admin_service.set_disabled(user_id, value, session)
    except ServiceError as e:
        return _err(e)
    log_action(
        "set_disabled",
        user_id=g.admin_user.id,
        resource_type="user",
        resource_id=target.id,
        details={"value": value, "target_email": target.email},
    )
    return _ok_refresh(f"{target.email} disabled set to {value}.")


@bp.route("/admin/api/users/<int:user_id>/platform-admin", methods=["POST"])
@require_platform_admin
def set_platform_admin(user_id):
    session = get_session()
    value = _truthy(_body().get("value"))
    operator = g.admin_user
    try:
        target = admin_service.set_platform_admin(user_id, value, session, actor_id=operator.id)
    except ServiceError as e:
        return _err(e)
    log_action(
        "set_platform_admin",
        user_id=operator.id,
        resource_type="user",
        resource_id=target.id,
        details={"value": value, "target_email": target.email},
    )
    return _ok_refresh(f"{target.email} platform-admin set to {value}.")


@bp.route("/admin/api/users/<int:user_id>/delete", methods=["POST"])
@require_platform_admin
def delete_user(user_id):
    session = get_session()
    operator = g.admin_user
    confirm = _body().get("confirm_name")
    try:
        # Typed-confirmation: operator must type the user's email.
        target = admin_service.user_detail(user_id, session)
        if confirm != target["email"]:
            raise ServiceError("Typed confirmation did not match the user's email.", 400)
        email = admin_service.delete_user(user_id, session, actor_id=operator.id)
    except ServiceError as e:
        return _err(e)
    log_action(
        "delete_user",
        user_id=operator.id,
        resource_type="user",
        resource_id=user_id,
        details={"target_email": email},
    )
    return _ok_refresh(f"Deleted user {email}.")


# --- organization mutations -------------------------------------------------


@bp.route("/admin/api/organizations/<int:org_id>/delete", methods=["POST"])
@require_platform_admin
def delete_organization(org_id):
    session = get_session()
    operator = g.admin_user
    confirm = _body().get("confirm_name")
    try:
        if operator.organization_id == org_id:
            raise ServiceError("You cannot delete the organization you belong to.", 400)
        org = admin_service.organization_detail(org_id, session)
        if confirm != org["name"]:
            raise ServiceError("Typed confirmation did not match the organization name.", 400)
        name = admin_service.delete_organization(org_id, session)
    except ServiceError as e:
        return _err(e)
    log_action(
        "delete_organization",
        user_id=operator.id,
        resource_type="organization",
        resource_id=org_id,
        details={"name": name},
    )
    return _ok_refresh(f"Deleted organization {name}.")


# --- helpers ----------------------------------------------------------------


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


def _ok_refresh(message):
    """Success for a state mutation: tell htmx to refresh the current view."""
    response = jsonify({"status": "success", "message": message})
    response.headers["HX-Refresh"] = "true"
    return response


# ADMIN_COOKIE re-exported for tests/readers that build admin requests.
__all__ = ["bp", "ADMIN_COOKIE"]
