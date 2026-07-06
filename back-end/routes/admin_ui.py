"""Server-rendered admin UI — Jinja2 + htmx under /admin/*.

Pages are guarded by require_platform_admin. The admin session is established by
POST /admin/login (sets the admin_session cookie); impersonation, resets, and
deletes are driven from these pages via htmx calls to the /admin/api/* endpoints
(routes/admin_api.py).
"""

from flask import Blueprint, g, redirect, render_template, request
from werkzeug.security import generate_password_hash

from controllers.database_controller import user_ops
from database.sessions import get_session
from services import admin_service
from services.audit import log_action
from utils.admin_auth import ADMIN_COOKIE, mint_admin_session, require_platform_admin
from utils.flask_app import limiter
from utils.passwords import needs_rehash, verify_password
from utils.settings import IN_PRODUCTION

bp = Blueprint("admin_ui", __name__)

ADMIN_COOKIE_PATH = "/admin"

# A fixed hash to verify against when the login email is absent or not a platform
# admin, so every login path does the same pbkdf2 work — no timing oracle that
# would let an attacker enumerate which emails are platform admins.
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-password", method="pbkdf2:sha256")


def _render(template, **ctx):
    """Render an admin template with the operator + CSRF token available to the
    base layout (set on g by the guard)."""
    ctx.setdefault("admin_user", g.get("admin_user"))
    ctx.setdefault("csrf_token", g.get("admin_csrf"))
    return render_template(template, **ctx)


def _set_admin_cookie(response, token):
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        httponly=True,
        samesite="Lax",
        secure=bool(IN_PRODUCTION),
        path=ADMIN_COOKIE_PATH,
    )
    return response


# --- auth -------------------------------------------------------------------


@bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        return render_template("admin/login.html")

    session = get_session()
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    user = user_ops.get_user_with_email(email, session)
    if (
        user
        and not isinstance(user, str)
        and getattr(user, "is_platform_admin", False)
        and not getattr(user, "disabled", False)
        and user.password
        and verify_password(user.password, password)
    ):
        if needs_rehash(user.password):
            # Legacy (pre-pbkdf2) hash: the user just proved the password, so
            # upgrade the stored hash in place — no forced reset.
            user_ops.reset_user_password(user.id, password)
        token, _csrf = mint_admin_session(user.id)
        response = redirect("/admin/")
        _set_admin_cookie(response, token)
        log_action("admin_login", user_id=user.id, resource_type="user", resource_id=user.id)
        return response

    # Equalize work on the failure path (absent / non-admin email) so response
    # time doesn't reveal which emails are platform admins.
    verify_password(_DUMMY_PASSWORD_HASH, password)
    log_action("admin_login_failed", details={"email": email})
    return render_template(
        "admin/login.html", error="Invalid credentials or not a platform admin."
    ), 401


@bp.route("/admin/logout", methods=["POST"])
@require_platform_admin
def logout():
    log_action("admin_logout", user_id=g.admin_user.id)
    response = redirect("/admin/login")
    response.delete_cookie(ADMIN_COOKIE, path=ADMIN_COOKIE_PATH)
    return response


# --- pages ------------------------------------------------------------------


@bp.route("/admin/", methods=["GET"])
@require_platform_admin
def dashboard():
    session = get_session()
    return _render("admin/dashboard.html", stats=admin_service.dashboard_stats(session))


@bp.route("/admin/organizations", methods=["GET"])
@require_platform_admin
def organizations():
    session = get_session()
    return _render(
        "admin/organizations.html", organizations=admin_service.list_organizations(session)
    )


@bp.route("/admin/organizations/<int:org_id>", methods=["GET"])
@require_platform_admin
def organization_detail(org_id):
    from services.exceptions import ServiceError

    session = get_session()
    try:
        org = admin_service.organization_detail(org_id, session)
    except ServiceError:
        return redirect("/admin/organizations")
    return _render("admin/organization_detail.html", org=org)


@bp.route("/admin/users", methods=["GET"])
@require_platform_admin
def users():
    session = get_session()
    q = request.args.get("q") or None
    user_list = admin_service.list_users(session, email=q)
    # htmx live-filter requests just want the rows.
    if request.headers.get("HX-Request") and request.args.get("partial"):
        return _render("admin/_user_rows.html", users=user_list)
    return _render(
        "admin/users.html",
        users=user_list,
        q=q or "",
        organizations=admin_service.list_organizations(session),
    )


@bp.route("/admin/users/<int:user_id>", methods=["GET"])
@require_platform_admin
def user_detail(user_id):
    from services.exceptions import ServiceError

    session = get_session()
    try:
        target = admin_service.user_detail(user_id, session)
    except ServiceError:
        return redirect("/admin/users")
    return _render(
        "admin/user_detail.html",
        target=target,
        organizations=admin_service.list_organizations(session),
    )


@bp.route("/admin/tasks", methods=["GET"])
@require_platform_admin
def tasks():
    session = get_session()
    return _render("admin/tasks.html", tasks=admin_service.tasks_across_orgs(session))


@bp.route("/admin/audit", methods=["GET"])
@require_platform_admin
def audit():
    session = get_session()
    return _render("admin/audit.html", entries=admin_service.recent_audit(session))


@bp.route("/admin/settings", methods=["GET", "POST"])
@require_platform_admin
def settings():
    """Site-wide settings: the theme every provider-facing page renders with
    (classes in static/app/bdk.css) and the export max-service-only toggle."""
    from controllers.database_controller import setting_ops

    session = get_session()
    error = None
    saved = False
    if request.method == "POST":
        theme = (request.form.get("site_theme") or "").strip()
        if theme not in setting_ops.SITE_THEMES:
            error = "Unknown theme."
        else:
            setting_ops.set_setting("site_theme", theme, session)
            max_service = "1" if request.form.get("export_max_service_only") else "0"
            setting_ops.set_setting("export_max_service_only", max_service, session)
            log_action(
                "set_site_settings",
                user_id=g.admin_user.id,
                details={"theme": theme, "export_max_service_only": max_service},
            )
            saved = True
    ctx = {
        "themes": setting_ops.SITE_THEMES,
        "current": setting_ops.get_site_theme(session),
        "max_service_only": setting_ops.export_max_service_only(session),
        "saved": saved,
        "error": error,
    }
    return _render("admin/settings.html", **ctx), (400 if error else 200)
