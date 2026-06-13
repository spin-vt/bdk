"""Server-rendered app pages (/org, /files, /map, /submissions, /setup) — the
strangler-fig seam for the redesigned UI.

These pin the page-session contract shared by every redesigned page:
  - an unauthenticated page load 302s to /login server-side (never a JSON 401
    and never the SPA's "Session expired!" modal);
  - an authenticated load renders HTML on the shared app `token` cookie (the
    same session the SPA and /api use — NOT the admin_session cookie);
  - every reserved page path is owned by the backend, so bringing a real page
    up later changes templates/handlers only, not the seam.
"""

import pytest

from tests.conftest import _db_reachable
from tests.conftest_helpers import login_page_session

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)

PAGE_PATHS = ["/org", "/files", "/map", "/submissions", "/setup"]


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_unauthenticated_page_redirects_to_login(client, path):
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/auth/login")


def test_root_routes_by_session(client):
    """The app's front door (nginx hands / to the backend at cutover):
    anonymous -> login, signed-in -> the map."""
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/auth/login")
    login_page_session(client, email="rootdoor@example.com")
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/map"


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_authenticated_page_renders(client, path):
    login_page_session(client, email="pages@example.com")
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


# Every page is real now — the setup page was the last placeholder to land.


def test_admin_session_does_not_grant_app_pages(client):
    """The admin_session cookie must not work as an app page session."""
    client.set_cookie("admin_session", "not-a-real-token")
    resp = client.get("/org")
    assert resp.status_code == 302


def test_trailing_slash_also_resolves(client):
    login_page_session(client, email="pages2@example.com")
    resp = client.get("/org/", follow_redirects=True)
    assert resp.status_code == 200


def test_default_theme_is_civic_light(client):
    """Civic Light is the default site theme: no override class on <body>, the
    stylesheet's default variable block applies."""
    login_page_session(client, email="pages3@example.com")
    resp = client.get("/org")
    assert b'class="app"' in resp.data
    assert b"theme-civic-vt" not in resp.data and b"theme-civic " not in resp.data


def test_assets_served(client):
    resp = client.get("/assets/bdk.css")
    assert resp.status_code == 200
    assert b"--accent: #005EA2" in resp.data


def test_shell_surfaces_request_errors(client):
    """A failed htmx request (an oversized upload's 413, a network drop) must
    never look like nothing happened — the shell carries a global handler."""
    login_page_session(client, email="errs@example.com")
    html = client.get("/org").get_data(as_text=True)
    assert "htmx:responseError" in html
    assert "too large to upload" in html and "smaller region" in html
    # Oversized picks are rejected client-side, before any request starts.
    assert "MAX_UPLOAD_BYTES" in html and "stopPropagation" in html


def test_header_filing_label_has_year_and_countdown(client, db_session):
    """'due Mar 3' alone is ambiguous: the label carries the year and a
    days-left/overdue readout; a filed filing shows when it was completed."""
    from datetime import date as _date

    from tests import conftest_helpers as H

    login_page_session(client, email="duelabel@example.com")
    from database.models import user as user_model
    from database.sessions import Session

    s = Session()
    try:
        u = s.query(user_model).filter_by(email="duelabel@example.com").one()
        org = H.make_org(s, name="duelabel-org")
        u.organization_id = org.id
        s.commit()
        folder = H.make_folder(s, org.id, deadline=_date(2025, 9, 1))

        html = client.get("/org").get_data(as_text=True)
        assert "due Sep 1, 2025" in html  # full date with year
        assert ("days left" in html) or ("days overdue" in html) or ("due today" in html)

        folder.status = "filed"
        folder.filed_at = _date(2025, 8, 15)
        s.commit()
        html = client.get("/org").get_data(as_text=True)
        assert "completed Aug 15, 2025" in html
    finally:
        s.close()
