"""Contract tests for the organization endpoints the org page relies on.

Fills the membership-flow gaps: join_organization (the email-token
request-to-join flow), the verify_token join branch that actually adds the
member, exit_organization, and delete_organization's wrong-name guard.
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    # Flask-Mail captured MAIL_SUPPRESS_SEND at import time (before TESTING was
    # set), so flip the live state: record_messages() still sees the sends.
    mail_state = app.extensions["mail"]
    prev_suppress, prev_sender = mail_state.suppress, mail_state.default_sender
    mail_state.suppress = True
    mail_state.default_sender = mail_state.default_sender or "bdk-test@example.com"
    with H.CsrfFlaskClient(app) as c:
        yield c
    mail_state.suppress, mail_state.default_sender = prev_suppress, prev_sender


def _register(client, email, password="Password123!"):
    resp = client.post("/api/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _verify(session, email):
    _get_user(session, email).verified = True
    session.commit()


def _org_with_admin(session, name="JoinableOrg", admin_email="admin@example.com"):
    org = H.make_org(session, name=name)
    admin = H.make_user(session, org_id=org.id, email=admin_email)
    admin.is_admin = True
    admin.verified = True
    session.commit()
    return org, admin


# ------------------------------------------------------------ join request


def test_join_organization_emails_the_org_admin(client, db_session):
    org, admin = _org_with_admin(db_session)
    _register(client, "joiner@example.com")
    _verify(db_session, "joiner@example.com")

    from utils.flask_app import mail

    with mail.record_messages() as outbox:
        resp = client.post("/api/join_organization", json={"name": org.name})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "success"
    assert len(outbox) == 1
    assert outbox[0].recipients == [admin.email]
    # The requester does NOT join yet — the admin's token click does that.
    assert _get_user(db_session, "joiner@example.com").organization_id is None


def test_join_organization_unknown_org_400(client, db_session):
    _register(client, "joiner2@example.com")
    _verify(db_session, "joiner2@example.com")
    resp = client.post("/api/join_organization", json={"name": "NoSuchOrg"})
    assert resp.status_code == 400
    assert "not found" in resp.get_json()["message"].lower()


def test_join_organization_requires_verified_email(client, db_session):
    org, _ = _org_with_admin(db_session)
    _register(client, "unverified@example.com")
    resp = client.post("/api/join_organization", json={"name": org.name})
    assert resp.status_code == 400
    assert "verify" in resp.get_json()["message"].lower()


def test_join_organization_org_without_admin_400(client, db_session):
    H.make_org(db_session, name="Headless")
    _register(client, "joiner3@example.com")
    _verify(db_session, "joiner3@example.com")
    resp = client.post("/api/join_organization", json={"name": "Headless"})
    assert resp.status_code == 400
    assert "admin" in resp.get_json()["message"].lower()


# ------------------------------------------------- verify_token join branch


def test_verify_token_join_branch_adds_the_member(client, db_session):
    org, _ = _org_with_admin(db_session, name="TokenOrg")
    _register(client, "tokenjoin@example.com")
    uid = _get_user(db_session, "tokenjoin@example.com").id

    from routes._email import create_email_token

    token = create_email_token(
        userid=uid, email="tokenjoin@example.com", operation="join_organization", org_id=org.id
    )
    resp = client.post("/api/verify_token", json={"token": token})
    assert resp.status_code == 200, resp.get_json()
    db_session.expire_all()
    assert _get_user(db_session, "tokenjoin@example.com").organization_id == org.id


def test_verify_token_join_branch_rejects_invalid_org_id(client, db_session):
    _register(client, "badorg@example.com")
    uid = _get_user(db_session, "badorg@example.com").id

    from routes._email import create_email_token

    token = create_email_token(
        userid=uid, email="badorg@example.com", operation="join_organization", org_id=-1
    )
    resp = client.post("/api/verify_token", json={"token": token})
    assert resp.status_code == 400
    db_session.expire_all()
    assert _get_user(db_session, "badorg@example.com").organization_id is None


# ------------------------------------------------------------ exit / delete


def test_exit_organization_roundtrip(client, db_session):
    _register(client, "leaver@example.com")
    org = H.make_org(db_session, name="LeaveMe")
    u = _get_user(db_session, "leaver@example.com")
    u.organization_id = org.id
    db_session.commit()

    resp = client.post("/api/exit_organization", json={"organizationName": "LeaveMe"})
    assert resp.status_code == 200, resp.get_json()
    db_session.expire_all()
    assert _get_user(db_session, "leaver@example.com").organization_id is None


def test_exit_organization_wrong_name_400(client, db_session):
    _register(client, "stayer@example.com")
    org = H.make_org(db_session, name="StayHere")
    u = _get_user(db_session, "stayer@example.com")
    u.organization_id = org.id
    db_session.commit()

    resp = client.post("/api/exit_organization", json={"organizationName": "WrongName"})
    assert resp.status_code == 400
    db_session.expire_all()
    assert _get_user(db_session, "stayer@example.com").organization_id == org.id


def test_delete_organization_wrong_name_400(client, db_session):
    from database.models import organization as org_model

    _register(client, "owner@example.com")
    org = H.make_org(db_session, name="KeepMe")
    u = _get_user(db_session, "owner@example.com")
    u.organization_id = org.id
    u.is_admin = True
    db_session.commit()

    resp = client.delete("/api/delete_organization", json={"organizationName": "NotKeepMe"})
    assert resp.status_code == 400
    assert db_session.query(org_model).filter(org_model.id == org.id).first() is not None
