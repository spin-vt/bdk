"""Audit logging.

``log_action`` appends one row to ``audit_log`` for security-relevant events:
login/logout, upload/edit/export, org create/delete, impersonation,
password resets, and role changes.

It writes in its OWN short-lived Session, deliberately isolated from the
caller's request session, and never raises — an audit-write failure must not
roll back or partially commit the action being audited.
"""

from flask import has_request_context, request

from database.models import audit_log
from database.sessions import Session
from utils.logger_config import logger


def current_ip():
    """Best-effort client IP. ProxyFix (x_for=1) already rewrites remote_addr
    from the trusted proxy's X-Forwarded-For, so trust that rather than parsing
    the raw header (which a client could spoof if the backend is reached
    directly)."""
    if not has_request_context():
        return None
    return request.remote_addr


def log_action(
    action,
    *,
    user_id=None,
    resource_type=None,
    resource_id=None,
    details=None,
    ip=None,
):
    if ip is None:
        ip = current_ip()
    session = Session()
    try:
        session.add(
            audit_log(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip=ip,
            )
        )
        session.commit()
    except Exception as e:  # never let auditing break the audited action
        session.rollback()
        logger.error(f"audit log_action failed for action={action!r}: {e}")
    finally:
        session.close()
