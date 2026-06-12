"""The Organization page (/org) — the first real server-rendered app page.

Pins:
  - rendering: provider name + BDC Provider ID form ("Not your FRN" copy, a
    "needed to export" warn chip only while the ID is empty), members list
    scoped to the viewer's org, and the invite affordance;
  - the no-organization state: a create-organization card, not an error;
  - the form posts (htmx): profile save (name + numeric-only provider id,
    provider_id stays an Integer — never the prototype's "0042-8817" string),
    create-organization, and their plain-words error states;
  - the legacy brand sync rule: organization.brand_name (which the legacy
    export still reads) follows the provider name unless it was deliberately
    set to something different;
  - CSRF: page POSTs without the double-submit header are rejected.
"""

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _login_with_org(client, db_session, email, org_name="PageOrg", provider_id=None, verified=True):
    login_page_session(client, email=email)
    org = H.make_org(db_session, name=org_name, provider_id=provider_id, brand_name=None)
    u = _get_user(db_session, email)
    u.organization_id = org.id
    u.is_admin = True
    u.verified = verified
    db_session.commit()
    return org


# ---------------------------------------------------------------- rendering


def test_org_page_renders_profile_and_members(client, db_session):
    org = _login_with_org(client, db_session, "render@example.com", provider_id=330054)
    H.make_user(db_session, org_id=org.id, email="teammate@example.com")

    html = client.get("/org").get_data(as_text=True)
    assert 'value="PageOrg"' in html
    assert 'value="330054"' in html
    assert "Not your FRN" in html
    assert "needed to export" not in html  # provider id present -> no warn chip
    assert "render@example.com" in html and "teammate@example.com" in html
    assert "Invite" in html


def test_org_page_warn_chip_when_provider_id_empty(client, db_session):
    _login_with_org(client, db_session, "warn@example.com", provider_id=None)
    html = client.get("/org").get_data(as_text=True)
    assert "needed to export" in html


def test_org_page_members_are_org_scoped(client, db_session):
    _login_with_org(client, db_session, "scoped@example.com")
    other = H.make_org(db_session, name="OtherOrg")
    H.make_user(db_session, org_id=other.id, email="stranger@example.com")

    html = client.get("/org").get_data(as_text=True)
    assert "stranger@example.com" not in html


def test_org_page_without_org_shows_create_card(client, db_session):
    login_page_session(client, email="orgless@example.com")
    html = client.get("/org").get_data(as_text=True)
    assert "Create your organization" in html
    assert "Not your FRN" not in html  # no profile form yet


# ------------------------------------------------------------- profile save


def test_profile_save_updates_name_and_provider_id(client, db_session):
    org = _login_with_org(client, db_session, "save@example.com")
    resp = client.post("/org/profile", data={"name": "Renamed Net", "provider_id": "445566"})
    assert resp.status_code == 200
    assert "Saved" in resp.get_data(as_text=True)
    db_session.expire_all()
    assert org.name == "Renamed Net"
    assert org.provider_id == 445566  # Integer, not a formatted string


def test_profile_save_rejects_non_numeric_provider_id(client, db_session):
    org = _login_with_org(client, db_session, "numeric@example.com", provider_id=330054)
    resp = client.post("/org/profile", data={"name": "PageOrg", "provider_id": "0042-8817"})
    assert resp.status_code == 200  # htmx re-render with the error, not a 4xx page
    body = resp.get_data(as_text=True)
    assert "numbers only" in body.lower()
    db_session.expire_all()
    assert org.provider_id == 330054  # unchanged


def test_profile_save_requires_a_name(client, db_session):
    org = _login_with_org(client, db_session, "noname@example.com")
    resp = client.post("/org/profile", data={"name": "   ", "provider_id": ""})
    body = resp.get_data(as_text=True)
    assert "name" in body.lower() and "Saved" not in body
    db_session.expire_all()
    assert org.name == "PageOrg"


def test_profile_save_duplicate_name_is_a_plain_error(client, db_session):
    H.make_org(db_session, name="TakenName")
    org = _login_with_org(client, db_session, "dupe@example.com")
    resp = client.post("/org/profile", data={"name": "TakenName", "provider_id": ""})
    body = resp.get_data(as_text=True)
    assert "already" in body.lower()
    db_session.expire_all()
    assert org.name == "PageOrg"


def test_profile_save_syncs_legacy_brand_unless_deliberate(client, db_session):
    """organization.brand_name (read by the legacy export) follows the provider
    name, except when it was deliberately set to a different brand."""
    org = _login_with_org(client, db_session, "brand@example.com")
    # brand empty -> save fills it
    client.post("/org/profile", data={"name": "SyncBrand", "provider_id": ""})
    db_session.expire_all()
    assert org.brand_name == "SyncBrand"

    # brand == old name -> rename keeps them in sync
    client.post("/org/profile", data={"name": "SyncBrand2", "provider_id": ""})
    db_session.expire_all()
    assert org.brand_name == "SyncBrand2"

    # a deliberately different brand is never clobbered
    org.brand_name = "Sold As Different"
    db_session.commit()
    client.post("/org/profile", data={"name": "SyncBrand3", "provider_id": ""})
    db_session.expire_all()
    assert org.name == "SyncBrand3"
    assert org.brand_name == "Sold As Different"


# ------------------------------------------------------------- creation


def test_create_org_from_page(client, db_session):
    from database.models import organization as org_model

    login_page_session(client, email="founder@example.com")
    u = _get_user(db_session, "founder@example.com")
    u.verified = True
    db_session.commit()

    resp = client.post("/org/create", data={"name": "Fresh ISP"})
    assert resp.status_code == 200
    assert resp.headers.get("HX-Redirect") == "/org"
    db_session.expire_all()
    org = db_session.query(org_model).filter(org_model.name == "Fresh ISP").one()
    u = _get_user(db_session, "founder@example.com")
    assert u.organization_id == org.id
    assert u.is_admin is True
    assert org.brand_name == "Fresh ISP"  # legacy brand starts in sync


def test_create_org_requires_verified_email(client, db_session):
    login_page_session(client, email="unverified-founder@example.com")
    resp = client.post("/org/create", data={"name": "Nope ISP"})
    body = resp.get_data(as_text=True)
    assert "verify" in body.lower()
    assert resp.headers.get("HX-Redirect") is None


def test_create_org_duplicate_name(client, db_session):
    H.make_org(db_session, name="Existing ISP")
    login_page_session(client, email="copycat@example.com")
    u = _get_user(db_session, "copycat@example.com")
    u.verified = True
    db_session.commit()

    resp = client.post("/org/create", data={"name": "Existing ISP"})
    assert "already" in resp.get_data(as_text=True).lower()


# ------------------------------------------------------------- CSRF


def test_page_posts_require_csrf_header(db_session):
    """Without the double-submit X-CSRF-TOKEN header the POST must not apply
    (the plain test client, unlike CsrfFlaskClient, doesn't echo the cookie)."""
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as plain:
        login_page_session(plain, email="csrf-page@example.com")
        org = H.make_org(db_session, name="CsrfOrg")
        u = _get_user(db_session, "csrf-page@example.com")
        u.organization_id = org.id
        db_session.commit()

        resp = plain.post("/org/profile", data={"name": "Hacked", "provider_id": ""})
        assert resp.status_code == 302  # bounced, not applied
        db_session.expire_all()
        assert org.name == "CsrfOrg"
