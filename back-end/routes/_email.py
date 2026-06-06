from datetime import datetime, timedelta

import jwt
from flask_mail import Message

from utils.flask_app import app, mail


def create_email_token(userid, email, operation, org_id=-1):
    expiration = datetime.now() + timedelta(minutes=15)
    email_token = jwt.encode(
        {
            "sub": {"id": userid, "email": email, "operation": operation, "org_id": org_id},
            "exp": expiration,
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return email_token


def send_verification_email_with_token(
    email, token, title, content, join_org=False, joining_email=""
):
    msg = Message(title, recipients=[email])
    msg.content_subtype = "html"  # This sets the message content type to HTML

    if join_org:
        message_start = f"Dear BDK User,<br><br>A user has requested to join your organization. Please forward the following token to {joining_email} and request them to enter it on the BDK website to "
    else:
        message_start = (
            "Dear BDK User,<br><br>Please enter the following token on the BDK website to "
        )

    message_body = f'{message_start}{content}.<br><br><strong>Verification Token:</strong><br><pre style="color: #00AAFF; background-color: #f0f0f0; padding: 10px; border-radius: 5px;">{token}</pre><br><br>Thank you,<br>BDK Team'

    msg.html = message_body.strip()  # Use msg.html for HTML content
    mail.send(msg)
