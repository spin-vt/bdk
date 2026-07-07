"""Server-rendered app pages — the redesigned UI, brought up page by page.

Each page lives at its final path (/org, /files, /map, /submissions, /setup)
and is served by the backend through nginx, beside the untouched SPA at /.
Pages share the app `token` session with the SPA and /api (NOT the admin
panel's separate admin_session cookie): an unauthenticated page load redirects
to /login server-side. Static assets (bdk.css, htmx) are served under /assets.

The site-wide theme (civic-light default; civic / civic-vt selectable in the
admin panel) is applied as a class on <body> by the base layout.
"""

from datetime import date
from functools import wraps

from flask import Blueprint, g, jsonify, make_response, redirect, render_template, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from controllers.database_controller import folder_ops, organization_ops, setting_ops, user_ops
from database.sessions import get_session
from services import fabric_service, filing_service, job_service
from services.audit import log_action
from services.exceptions import ServiceError

bp = Blueprint(
    "app_pages",
    __name__,
    template_folder="../templates",
    static_folder="../static/app",
    static_url_path="/assets",
)


FILING_COOKIE = "bdk_filing"


@bp.app_template_filter("friendly_date")
def friendly_date(iso):
    """ISO date -> 'Mar 3, 2026' (used by the switcher dropdown)."""
    try:
        return date.fromisoformat(iso).strftime("%b %-d, %Y")
    except (TypeError, ValueError):
        return iso


def current_folder(me, session):
    """THE selected filing — the one every page (map, files, submissions, the
    header) is looking at. The switcher sets a cookie; an absent or invalid
    cookie (deleted filing, another org's) falls back to the org's latest
    upload filing. One notion of "current" for the whole app."""
    if not me or not me.organization_id:
        return None
    raw = request.cookies.get(FILING_COOKIE)
    if raw and raw.isdigit():
        f = folder_ops.get_folder_with_id(folderid=int(raw), session=session)
        if (
            f is not None
            and not isinstance(f, str)
            and f.type == "upload"
            and f.organization_id == me.organization_id
        ):
            return f
    return folder_ops.get_upload_folder(orgid=me.organization_id, folderid=None, session=session)


@bp.context_processor
def _inject_chrome():
    """Everything the base layout's header needs, on every page render: the
    site theme and the filing-switcher state for the logged-in user's org."""
    session = get_session()
    ctx = {"site_theme": setting_ops.get_site_theme(session)}
    identity = g.get("page_identity")
    # Initial job pill/tray state, server-rendered so there's no flash of a
    # wrong state before the SSE stream connects and takes over.
    org_id = None
    user_val = None
    if identity:
        user_val = user_ops.get_user_with_id(userid=identity["id"], session=session)
        org_id = user_val.organization_id if user_val else None
    ctx["jobs"] = job_service.org_jobs_snapshot(org_id, session)
    if user_val is not None:
        ctx["user_verified"] = bool(user_val.verified)
    if identity:
        data = filing_service.switcher_data(identity["id"], session)
        ctx["switcher"] = data
        selected = current_folder(user_val, session)
        ctx["current_folder_id"] = selected.id if selected is not None else None
        current = None
        if selected is not None:
            current = next((f for f in data["filings"] if f["id"] == selected.id), None)
        if current:
            ctx["filing_name"] = current["label"]
            ctx["filing_status"] = current["status"]
            if current["status"] == "filed" and selected is not None and selected.filed_at:
                ctx["filing_filed_on"] = selected.filed_at.strftime("%b %-d, %Y")
            elif current["due"]:
                due = date.fromisoformat(current["due"])
                days = (due - date.today()).days
                ctx["filing_due"] = due.strftime("%b %-d, %Y")
                ctx["filing_due_rel"] = (
                    "due today"
                    if days == 0
                    else f"{days} days left"
                    if days > 0
                    else f"{-days} days overdue"
                )
        # The header debt badge ("N tasks to finish" / "Ready to submit"):
        # what still stands between the current filing and a submission. A
        # wrong-vintage fabric isn't a debt (it's allowed) but turns the
        # ready badge into a warning.
        if selected is not None and selected.status != "filed":
            ctx["debts"] = filing_service.submission_debts(user_val.id, selected.id, session)
            ctx["fabric_warning"] = fabric_service.fabric_vintage_warning(selected.id, session)
    return ctx


def page_session_required(view):
    """Validate the shared app `token` cookie; bounce to the new shell's
    login otherwise (a non-SPA login target, required before cutover).
    Passes the JWT identity to the view as `identity`."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            identity = get_jwt_identity()
        except Exception:
            return redirect("/auth/login")
        g.page_identity = identity
        return view(*args, identity=identity, **kwargs)

    return wrapper


@bp.route("/healthz")
def healthz():
    """Liveness probe for the CI boot smoke and deploy tooling. Deliberately
    touches nothing (no auth, no DB): it answers "is the WSGI app up", so a
    degraded dependency can't wedge the container health loop."""
    return jsonify({"status": "ok"})


@bp.route("/", strict_slashes=False)
def root():
    """The app's front door (live once nginx routes / here at cutover):
    a signed-in user lands on the map, everyone else on the login page."""
    try:
        verify_jwt_in_request()
        return redirect("/map")
    except Exception:
        return redirect("/auth/login")


def _member_rows(org, me):
    rows = []
    for member in sorted(org.users, key=lambda u: u.email):
        role = "admin" if member.is_admin else "member"
        if member.id == me.id:
            role += " · you"
        rows.append({"email": member.email, "role": role})
    return rows


@bp.route("/org", strict_slashes=False)
@page_session_required
def org_page(identity):
    session = get_session()
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    org = me.organization if me else None
    return render_template(
        "app/org.html",
        org=org,
        members=_member_rows(org, me) if org else [],
        saved=False,
        error=None,
    )


@bp.route("/org/profile", methods=["POST"])
@page_session_required
def org_profile_save(identity):
    """htmx save of the provider profile; re-renders the card with Saved ✓ or
    a plain-words error. provider_id stays an Integer (it's the numeric BDC
    Provider ID, never the prototype's dash-formatted string)."""
    session = get_session()
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    org = me.organization if me else None
    if org is None:
        return redirect("/org")

    name = (request.form.get("name") or "").strip()
    pid_raw = (request.form.get("provider_id") or "").strip()

    error = None
    provider_id = None
    if not name:
        error = "Please enter a provider name."
    elif pid_raw and not pid_raw.isdigit():
        error = "Provider ID is numbers only — the ID from your BDC account, not your FRN."
    elif name != org.name and organization_ops.get_organization_with_orgname(
        org_name=name, session=session
    ):
        error = "That organization name is already in use."
    if error:
        return render_template("app/_org_profile_card.html", org=org, saved=False, error=error)
    if pid_raw:
        provider_id = int(pid_raw)

    # The legacy export still reads organization.brand_name: keep it following
    # the provider name unless it was deliberately set to a different brand.
    if not org.brand_name or org.brand_name == org.name:
        org.brand_name = name
    org.name = name
    org.provider_id = provider_id
    session.commit()
    return render_template("app/_org_profile_card.html", org=org, saved=True, error=None)


@bp.route("/org/create", methods=["POST"])
@page_session_required
def org_create(identity):
    """htmx create-organization (the no-org state); mirrors the rules of
    POST /api/create_organization. On success the page reloads via HX-Redirect
    so the header chrome (filing switcher, job pill) picks up the new org."""
    session = get_session()
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    name = (request.form.get("name") or "").strip()

    error = None
    if me is None or me.organization is not None:
        return redirect("/org")
    if not me.verified:
        error = "Please verify your email address first — check your inbox."
    elif not name:
        error = "Please enter an organization name."
    elif organization_ops.get_organization_with_orgname(org_name=name, session=session):
        error = "That organization name is already in use."
    if error:
        return render_template("app/_org_create_card.html", name=name, error=error)

    new_org = organization_ops.create_organization(org_name=name, session=session)
    new_org.brand_name = name  # legacy brand starts in sync with the name
    me.organization_id = new_org.id
    me.is_admin = True
    session.commit()
    log_action(
        "org_create",
        user_id=me.id,
        resource_type="organization",
        resource_id=new_org.id,
        details={"name": name},
    )
    resp = make_response("", 200)
    resp.headers["HX-Redirect"] = "/org"
    return resp


# /files is served by routes/files_page.py (the real page).


def _select_filing_response(folder_id, location=None):
    """Set the selected-filing cookie and send the browser somewhere (htmx:
    HX-Refresh reloads in place, HX-Redirect navigates)."""
    resp = make_response("", 200)
    resp.set_cookie(FILING_COOKIE, str(folder_id), max_age=90 * 24 * 3600, path="/", samesite="Lax")
    if location:
        resp.headers["HX-Redirect"] = location
    else:
        resp.headers["HX-Refresh"] = "true"
    return resp


@bp.route("/filing/select/<int:folder_id>", methods=["POST"])
@page_session_required
def select_filing(identity, folder_id):
    """Switch which filing the whole app is looking at (map, files, plans,
    submissions, the header — all of it)."""
    session = get_session()
    me = user_ops.get_user_with_id(userid=identity["id"], session=session)
    f = folder_ops.get_folder_with_id(folderid=folder_id, session=session)
    if (
        f is None
        or isinstance(f, str)
        or f.type != "upload"
        or not me
        or f.organization_id != me.organization_id
    ):
        return redirect("/map")
    return _select_filing_response(f.id)


def _filing_modal_ctx(identity, session, error=None, form=None):
    """The create-a-filing modal's state: pickable years (June 2022 through
    the next window's year) and the org's filings as copy-from options."""
    from services import filing_windows

    data = filing_service.switcher_data(identity["id"], session)
    next_year = filing_windows.next_window(date.today()).year
    return {
        "filings": data["filings"],
        "years": list(range(next_year, 2021, -1)),
        "error": error,
        "form": form or {},
    }


@bp.route("/filing/modals/new")
@page_session_required
def filing_new_modal(identity):
    """The switcher's "Create new filing…" — any opened window (e.g. an org
    bringing its old filings in), with a copy-from picker."""
    session = get_session()
    return render_template("app/_filing_new_modal.html", **_filing_modal_ctx(identity, session))


@bp.route("/filing/create", methods=["POST"])
@page_session_required
def create_filing(identity):
    """Create the picked window's filing (copying from the chosen source, the
    nearest-earlier default, or scratch), select it, and land on the fabric
    tab. A bad pick re-renders the modal with the error."""
    session = get_session()
    try:
        new_folder = filing_service.start_filing_for_window(
            identity["id"],
            request.form.get("year"),
            request.form.get("month"),
            session,
            source=request.form.get("source") or "auto",
        )
    except ServiceError as e:
        return render_template(
            "app/_filing_new_modal.html",
            **_filing_modal_ctx(identity, session, error=e.message, form=request.form),
        )
    return _select_filing_response(new_folder.id, location="/files?tab=fabric")


@bp.route("/filing/start-next", methods=["POST"])
@page_session_required
def start_next_filing(identity):
    """The switcher's explicit "+ Start the <window> filing": carries the
    current filing forward (or starts empty for a first-time org), selects the
    new filing, and lands on the fabric tab — the one thing the new window
    needs is its fabric."""
    session = get_session()
    try:
        new_folder = filing_service.start_next_filing(identity["id"], session)
    except ServiceError as e:
        return render_template("app/_filing_start_error.html", error=e.message)
    return _select_filing_response(new_folder.id, location="/files?tab=fabric")


# /map is served by routes/map_page.py (the real page).


# /submissions is served by routes/submissions_page.py (the real page).


# /setup is served by routes/setup_page.py (the real page).
