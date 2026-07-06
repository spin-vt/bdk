import uuid
from datetime import UTC, datetime, timedelta

import jwt
from flask_mail import Message
from sqlalchemy.exc import IntegrityError

from utils.flask_app import app, mail

# Email tokens share the signing key with the session JWTs, so they carry an
# explicit audience and the decoders require it — a session token can never
# pass as an email token (or vice versa: session decoding requires claims
# email tokens don't have).
EMAIL_TOKEN_AUDIENCE = "bdk-email"


# How long a verify/reset/join link stays valid. An hour, not minutes: users
# routinely open these emails well after they arrive, and an expired link
# reads as a broken product. Tokens are not single-use, so this is also the
# replay window for an already-used link — keep it to hours, not days.
EMAIL_TOKEN_LIFETIME = timedelta(minutes=60)


def create_email_token(userid, email, operation, org_id=-1):
    # Expiry must be timezone-aware UTC: PyJWT treats a naive datetime as UTC,
    # so naive local time on a non-UTC host mints already-expired tokens.
    expiration = datetime.now(UTC) + EMAIL_TOKEN_LIFETIME
    email_token = jwt.encode(
        {
            "sub": {"id": userid, "email": email, "operation": operation, "org_id": org_id},
            "exp": expiration,
            "aud": EMAIL_TOKEN_AUDIENCE,
            # One-time-use handle: consume_email_token records it on first
            # successful use, so a leaked/reused link can't be replayed.
            "jti": uuid.uuid4().hex,
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return email_token


def consume_email_token(decoded):
    """One-time-use gate. True the first time a decoded token is consumed;
    False on replay or when the token has no jti (minted before stamping —
    those age out within EMAIL_TOKEN_LIFETIME of the deploy).

    Call it after the domain checks pass and before mutating anything. The
    unique constraint on jti is the actual gate, so two concurrent uses of
    the same token can't both win. Own short session on purpose: the
    IntegrityError rollback must not discard request-scoped work."""
    from database.models import used_email_token
    from database.sessions import Session

    jti = decoded.get("jti")
    if not jti:
        return False
    # Column is a naive-UTC DateTime like the rest of the schema.
    now = datetime.now(UTC).replace(tzinfo=None)
    expires_at = datetime.fromtimestamp(decoded["exp"], UTC).replace(tzinfo=None)
    session = Session()
    try:
        # Opportunistic prune: expired rows guard nothing (their JWTs are
        # already dead), so the table stays bounded by the token lifetime.
        session.query(used_email_token).filter(used_email_token.expires_at < now).delete()
        session.add(used_email_token(jti=jti, expires_at=expires_at))
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False
    finally:
        session.close()


def send_verification_email_with_token(
    email, token, title, content, join_org=False, joining_email="", link_path=None
):
    """link_path (e.g. "/auth/reset/<token>") adds a clickable link for the
    new app's pages; the raw token stays in the body for the SPA's
    paste-the-token flows until cutover."""
    import os

    msg = Message(title, recipients=[email])
    msg.content_subtype = "html"  # This sets the message content type to HTML

    if join_org:
        message_start = f"Dear BDK User,<br><br>A user has requested to join your organization. Please forward the following token to {joining_email} and request them to enter it on the BDK website to "
    else:
        message_start = (
            "Dear BDK User,<br><br>Please enter the following token on the BDK website to "
        )

    link_html = ""
    if link_path:
        base = (os.getenv("PUBLIC_BASE_URL") or "http://localhost").rstrip("/")
        link_html = f'<br><br><strong>Or just click:</strong> <a href="{base}{link_path}">{base}{link_path}</a>'

    message_body = f'{message_start}{content}.<br><br><strong>Verification Token:</strong><br><pre style="color: #00AAFF; background-color: #f0f0f0; padding: 10px; border-radius: 5px;">{token}</pre>{link_html}<br><br>Thank you,<br>BDK Team'

    msg.html = message_body.strip()  # Use msg.html for HTML content
    mail.send(msg)
