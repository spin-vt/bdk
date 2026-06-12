"""Platform-admin business logic.

Plain-Python service functions used by the admin API/UI. Reads query across all
organizations (the operator sees everything); mutations reuse the existing ops
where possible and raise ServiceError on expected failures. Auditing is done by
the route handlers (they hold the request/IP context).
"""

import secrets
from datetime import timedelta

from flask_jwt_extended import create_access_token

from controllers.database_controller import user_ops
from database.models import audit_log, celerytaskinfo, folder, organization, user
from services.exceptions import ServiceError

# Impersonation tokens are deliberately short-lived: they bypass the per-request
# platform-admin/disabled re-check that admin_session gets, and "stop" can only
# delete the browser cookie (no server-side revocation), so a captured token
# must not stay valid for the app's default 7-day access window.
IMPERSONATION_TTL = timedelta(minutes=30)

# --- reads ------------------------------------------------------------------


def dashboard_stats(session):
    return {
        "organizations": session.query(organization).count(),
        "users": session.query(user).count(),
        "filings": session.query(folder).filter(folder.type == "upload").count(),
        "exports": session.query(folder).filter(folder.type == "export").count(),
        "platform_admins": session.query(user).filter(user.is_platform_admin.is_(True)).count(),
        "recent_tasks": _serialize_tasks(
            session.query(celerytaskinfo)
            .order_by(celerytaskinfo.start_time.desc().nullslast())
            .limit(10)
            .all()
        ),
    }


def list_organizations(session):
    orgs = session.query(organization).order_by(organization.name).all()
    out = []
    for org in orgs:
        out.append(
            {
                "id": org.id,
                "name": org.name,
                "provider_id": org.provider_id,
                "brand_name": org.brand_name,
                "user_count": session.query(user).filter(user.organization_id == org.id).count(),
                "filing_count": session.query(folder)
                .filter(folder.organization_id == org.id, folder.type == "upload")
                .count(),
            }
        )
    return out


def organization_detail(org_id, session):
    org = session.query(organization).filter(organization.id == org_id).first()
    if not org:
        raise ServiceError("Organization not found", 404)
    return {
        "id": org.id,
        "name": org.name,
        "provider_id": org.provider_id,
        "brand_name": org.brand_name,
        "users": [_serialize_user(u) for u in org.users],
        "filings": [
            {
                "id": f.id,
                "name": f.name,
                "type": f.type,
                "deadline": f.deadline.strftime("%Y-%m-%d") if f.deadline else None,
            }
            for f in org.folders
        ],
    }


def list_users(session, *, email=None, organization_id=None):
    q = session.query(user)
    if email:
        q = q.filter(user.email.ilike(f"%{email}%"))
    if organization_id:
        q = q.filter(user.organization_id == organization_id)
    return [_serialize_user(u, session=session) for u in q.order_by(user.email).all()]


def user_detail(user_id, session):
    u = session.query(user).filter(user.id == user_id).first()
    if not u:
        raise ServiceError("User not found", 404)
    return _serialize_user(u, session=session)


def tasks_across_orgs(session, *, limit=100):
    return _serialize_tasks(
        session.query(celerytaskinfo)
        .order_by(celerytaskinfo.start_time.desc().nullslast())
        .limit(limit)
        .all()
    )


# --- mutations --------------------------------------------------------------


def mint_impersonation_token(target_id, operator_id, session):
    """Mint a short-lived APP token (the SPA's `token` cookie) for the target
    user, tagged with the operator id so the app can show the impersonation
    banner and the action is auditable. Never touches the admin_session cookie.

    Refuses unsafe targets: yourself (pointless), another platform admin
    (lateral privilege / a way to mint a foreign-identity token), and disabled
    users (would defeat the soft-disable)."""
    target = _require_user(target_id, session)
    if target.id == operator_id:
        raise ServiceError("You cannot impersonate yourself.", 400)
    if target.is_platform_admin:
        raise ServiceError("Refusing to impersonate another platform admin.", 400)
    if target.disabled:
        raise ServiceError("Cannot impersonate a disabled user; enable them first.", 400)
    token = create_access_token(
        identity={"id": target.id, "impersonator": operator_id},
        expires_delta=IMPERSONATION_TTL,
    )
    return token, target


def reset_password_temp(user_id, session):
    """Set a random temporary password and return it ONCE (the operator relays
    it). The plaintext is never stored or logged."""
    u = _require_user(user_id, session)
    temp_password = secrets.token_urlsafe(12)
    user_ops.reset_user_password(u.id, temp_password)
    return temp_password, u


def send_password_reset_email(user_id, session):
    """Send the standard password-reset email to the user (reuses the app flow)."""
    from routes._email import create_email_token, send_verification_email_with_token

    u = _require_user(user_id, session)
    email_token = create_email_token(userid=u.id, email=u.email, operation="reset_password")
    send_verification_email_with_token(
        email=u.email,
        token=email_token,
        title="Reset Your Password for BDK",
        content="reset your password",
        link_path=f"/auth/reset/{email_token}",
    )
    return u


def create_user(email, session, *, organization_id=None):
    """Operator-created account (Decisions #4 — the real-world path): born
    VERIFIED (the operator vouches; no email round-trip), optionally attached
    to an org, with a random temporary password returned ONCE. The operator
    relays it (or follows up with the reset-email button — the activation
    flow)."""
    from werkzeug.security import generate_password_hash

    from utils.validation import is_valid_email

    email = (email or "").strip()
    if not is_valid_email(email):
        raise ServiceError("Please provide a valid email address.", 400)
    if session.query(user).filter(user.email == email).first() is not None:
        raise ServiceError("A user with that email already exists.", 400)
    if organization_id is not None:
        org = session.query(organization).filter(organization.id == organization_id).first()
        if org is None:
            raise ServiceError("Organization not found", 404)
    temp_password = secrets.token_urlsafe(12)
    u = user(
        email=email,
        password=generate_password_hash(temp_password, method="pbkdf2:sha256"),
        verified=True,
        organization_id=organization_id,
    )
    session.add(u)
    session.commit()
    return temp_password, u


def create_organization_admin(name, session, *, provider_id=None):
    """Create an org from the admin panel. Brand follows the name at birth
    (the same legacy-sync rule the org page keeps); provider id numeric."""
    name = (name or "").strip()
    if not name:
        raise ServiceError("Please provide an organization name.", 400)
    if session.query(organization).filter(organization.name == name).first() is not None:
        raise ServiceError("That organization name is already in use.", 400)
    pid = None
    if provider_id not in (None, ""):
        if not str(provider_id).strip().isdigit():
            raise ServiceError(
                "Provider ID is numbers only — the ID from the BDC account, not the FRN.", 400
            )
        pid = int(str(provider_id).strip())
    org = organization(name=name, provider_id=pid, brand_name=name)
    session.add(org)
    session.commit()
    return org


def set_organization(user_id, organization_id, session):
    """Attach a user to an org (or detach with None). Org-admin never rides
    along — landing in an org (or leaving one) always means plain member."""
    u = _require_user(user_id, session)
    if organization_id is None:
        u.organization_id = None
        u.is_admin = False
        session.commit()
        return u, None
    org = session.query(organization).filter(organization.id == organization_id).first()
    if org is None:
        raise ServiceError("Organization not found", 404)
    u.organization_id = org.id
    u.is_admin = False
    session.commit()
    return u, org


def set_org_admin(user_id, value, session):
    """The org-level admin flag (distinct from platform admin)."""
    u = _require_user(user_id, session)
    if u.organization_id is None:
        raise ServiceError("The user isn't in an organization.", 400)
    u.is_admin = bool(value)
    session.commit()
    return u


def set_verified(user_id, value, session):
    u = _require_user(user_id, session)
    u.verified = bool(value)
    session.commit()
    return u


def set_disabled(user_id, value, session):
    u = _require_user(user_id, session)
    u.disabled = bool(value)
    session.commit()
    return u


def set_platform_admin(user_id, value, session, *, actor_id):
    """Grant/revoke platform-admin. An operator cannot revoke their own platform
    admin (locking themselves or everyone out)."""
    value = bool(value)
    if not value and user_id == actor_id:
        raise ServiceError("You cannot revoke your own platform-admin access.", 400)
    u = _require_user(user_id, session)
    u.is_platform_admin = value
    session.commit()
    return u


def delete_user(user_id, session, *, actor_id):
    if user_id == actor_id:
        raise ServiceError("You cannot delete your own account from the admin panel.", 400)
    u = _require_user(user_id, session)
    email = u.email
    session.delete(u)
    session.commit()
    return email


def delete_organization(org_id, session):
    """Delete an org and all its data via the same async task the app uses (runs
    eagerly under tests, queued in prod)."""
    from controllers.celery_controller.celery_tasks import async_org_delete

    org = session.query(organization).filter(organization.id == org_id).first()
    if not org:
        raise ServiceError("Organization not found", 404)
    name = org.name
    async_org_delete.apply_async(args=[org_id])
    return name


# --- helpers ----------------------------------------------------------------


def _require_user(user_id, session):
    u = session.query(user).filter(user.id == user_id).first()
    if not u:
        raise ServiceError("User not found", 404)
    return u


def _serialize_user(u, session=None):
    org_name = u.organization.name if u.organization else None
    return {
        "id": u.id,
        "email": u.email,
        "verified": u.verified,
        "disabled": u.disabled,
        "is_admin": u.is_admin,
        "is_platform_admin": u.is_platform_admin,
        "organization_id": u.organization_id,
        "organization_name": org_name,
    }


def _serialize_tasks(tasks):
    return [
        {
            "id": t.id,
            "task_id": t.task_id,
            "status": t.status,
            "operation_type": t.operation_type,
            "operation_detail": t.operation_detail,
            "user_email": t.user_email,
            "organization_id": t.organization_id,
            "start_time": t.start_time.isoformat() if t.start_time else None,
            "runtime": t.runtime,
        }
        for t in tasks
    ]


# audit_log is imported for callers that want to read the audit trail in the UI.
def recent_audit(session, *, limit=200):
    rows = session.query(audit_log).order_by(audit_log.ts.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "user_id": r.user_id,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "details": r.details,
            "ip": r.ip,
        }
        for r in rows
    ]
