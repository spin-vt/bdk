"""Layer 3 — API / auth smoke tests through the real HTTP routes.

Importing utils.flask_app calls create_app()/init_db(), which needs the DB up,
so the whole module skips if Postgres is unreachable. We exercise register /
login / logout / org creation / filing creation / listing through the actual
Flask routes, plus an authz check (cannot touch another org's filing).
"""

import io
import json

import pytest

from tests import conftest_helpers as H
from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    """Flask test client against the truncated test DB. db_session is requested
    so tables exist and are cleaned between tests. Importing routes registers
    all endpoints onto the app."""
    import routes  # noqa: F401  (decorators attach routes to utils.flask_app.app)
    from utils.flask_app import app

    app.config["TESTING"] = True
    # JWT_VERIFY_SUB=False is now set in the app Config (the dict-identity fix for
    # flask-jwt-extended 4.7), so these tests exercise the real production config.
    with H.CsrfFlaskClient(app) as c:
        yield c


def _register(client, email, password="Password123!"):
    return client.post("/api/register", json={"email": email, "password": password})


def _verify_user(email):
    """Flip the verified flag directly (email verification is out of band)."""
    from database.models import user
    from database.sessions import Session

    s = Session()
    try:
        u = s.query(user).filter(user.email == email).one()
        u.verified = True
        s.commit()
        return u.id
    finally:
        s.close()


def test_register_sets_cookie_and_returns_200(client):
    resp = _register(client, "alice@example.com")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"
    # Register issues an access cookie immediately.
    assert "token" in resp.headers.get("Set-Cookie", "")


def test_protected_endpoint_requires_auth(client):
    """No cookie -> 401 from a @jwt_required endpoint."""
    resp = client.get("/api/user")
    assert resp.status_code == 401


def test_login_then_protected_endpoint_ok(client):
    _register(client, "bob@example.com")
    # New client cookie jar already holds the register token, but test login too.
    login = client.post("/api/login", json={"email": "bob@example.com", "password": "Password123!"})
    assert login.status_code == 200
    assert login.get_json()["status"] == "success"

    resp = client.get("/api/user")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["userinfo"]["email"] == "bob@example.com"


def test_login_bad_credentials(client):
    _register(client, "carol@example.com")
    login = client.post("/api/login", json={"email": "carol@example.com", "password": "wrong"})
    # Route returns 200 with an error status payload for bad creds.
    assert login.get_json()["status"] == "error"


def test_logout_clears_cookie(client):
    _register(client, "dave@example.com")
    resp = client.post("/api/logout")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"


def test_create_organization(client):
    _register(client, "erin@example.com")
    _verify_user("erin@example.com")
    resp = client.post("/api/create_organization", json={"orgName": "Erin ISP"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "success"


def test_create_organization_requires_verified(client):
    _register(client, "frank@example.com")  # not verified
    resp = client.post("/api/create_organization", json={"orgName": "Frank ISP"})
    assert resp.status_code == 400
    assert "verify" in resp.get_json()["message"].lower()


@pytest.fixture()
def no_tiles(monkeypatch):
    """Tile generation (tippecanoe) is an external binary covered by Layer 5;
    stub it out so the eager submit-data celery chain completes for the API
    smoke tests."""
    import controllers.celery_controller.celery_tasks as ct
    import controllers.database_controller.vt_ops as vt

    monkeypatch.setattr(vt, "create_tiles", lambda *a, **k: None)
    monkeypatch.setattr(ct.vt_ops, "create_tiles", lambda *a, **k: None)


def _create_filing(client, deadline="2024-05-14"):
    """Drive the real multipart submit-data route (operation 2: new filing from
    scratch) with a tiny fabric CSV. Celery runs eagerly (autouse fixture)."""
    # Note: in fabric_data_temp, unit_count and land_use_code are INTEGER, so
    # they must not be empty strings (Postgres COPY rejects "" for int).
    csv = (
        '"location_id","address_primary","city","state","zip","zip_suffix",'
        '"unit_count","bsl_flag","building_type_code","land_use_code",'
        '"address_confidence_code","county_geoid","block_geoid","h3_9",'
        '"latitude","longitude","fcc_rel"\n'
        '1,"1 Main St","Roanoke","VA","24011","1234","1",True,"R","1100",'
        '"HIGH","51770","510770001001000","8928308280fffff",37.27,-79.94,"rel"\n'
    )
    file_data = {
        "name": "fabric.csv",
    }
    data = {
        "fileData": json.dumps(file_data),
        "importFolder": "-1",
        "deadline": deadline,
        "file": (io.BytesIO(csv.encode("utf-8")), "fabric.csv"),
    }
    return client.post("/api/submit-data/-1", data=data, content_type="multipart/form-data")


def test_create_and_list_filing(client, no_tiles):
    _register(client, "grace@example.com")
    _verify_user("grace@example.com")
    org = client.post("/api/create_organization", json={"orgName": "Grace ISP"})
    assert org.status_code == 200

    created = _create_filing(client)
    assert created.status_code == 200, created.get_json()
    assert created.get_json()["status"] == "success"

    listing = client.get("/api/folders-with-deadlines")
    assert listing.status_code == 200
    folders = listing.get_json()
    assert isinstance(folders, list)
    assert len(folders) == 1
    assert folders[0]["deadline"] == "2024-05-14"


def test_cannot_access_other_orgs_filing(client, no_tiles):
    """Authz: a user in org B cannot read served-data for org A's folder."""
    from database.models import folder, user
    from database.sessions import Session

    # User A creates an org + a filing.
    _register(client, "heidi@example.com")
    _verify_user("heidi@example.com")
    client.post("/api/create_organization", json={"orgName": "Heidi ISP"})
    assert _create_filing(client).status_code == 200

    s = Session()
    try:
        a_user = s.query(user).filter(user.email == "heidi@example.com").one()
        a_folder = s.query(folder).filter(folder.organization_id == a_user.organization_id).one()
        a_folder_id = a_folder.id
    finally:
        s.close()

    # Fresh client = User B, different org.
    from utils.flask_app import app

    with app.test_client() as c2:
        c2.post("/api/register", json={"email": "ivan@example.com", "password": "Password123!"})
        _verify_user("ivan@example.com")
        c2.post("/api/create_organization", json={"orgName": "Ivan ISP"})

        resp = c2.get(f"/api/served-data/{a_folder_id}")
        # Route returns 400 with an "not belong to your organization" message,
        # in the unified {status:error, message} shape.
        assert resp.status_code in (400, 403), resp.get_json()
        body = resp.get_json()
        assert body["status"] == "error"
        assert "organization" in body["message"].lower()


def test_unhandled_exception_returns_json_500(client, monkeypatch):
    """An unexpected error returns a clean JSON 500 in the unified shape, not an
    HTML stack trace (the global error handler)."""
    from utils.flask_app import app

    # TESTING=True makes Flask re-raise instead of invoking error handlers; turn
    # that off so we exercise the real handler the way production does.
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

    _register(client, "judy@example.com")
    _verify_user("judy@example.com")

    import controllers.database_controller.folder_ops as fo

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(fo, "folder_belongs_to_organization", boom)

    resp = client.get("/api/served-data/5")
    assert resp.status_code == 500
    body = resp.get_json()  # None if the body wasn't JSON (e.g. an HTML page)
    assert body is not None, "500 body was not JSON"
    assert body["status"] == "error"
    assert "message" in body
