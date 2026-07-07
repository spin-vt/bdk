"""Auth rate limiting tests.

The limiter is disabled across the suite (RATELIMIT_ENABLED=false) so in-memory
counts don't leak between tests. This test enables it locally, hammers a couple
of auth endpoints past their per-minute limit, and asserts a 429 in the unified
shape — then disables it again so it can't affect other tests.
"""

import pytest

from tests.conftest import _db_reachable

pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="integration Postgres not reachable on localhost:5433"
)


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def rate_limiting_on():
    from utils.flask_app import limiter

    limiter.enabled = True
    try:
        yield limiter
    finally:
        limiter.enabled = False


def test_login_is_rate_limited(client, rate_limiting_on):
    codes = [
        client.post("/auth/login", data={"email": "x@example.com", "password": "nope"}).status_code
        for _ in range(15)
    ]
    assert 429 in codes, codes
    over = client.post("/auth/login", data={"email": "x@example.com", "password": "nope"})
    assert over.status_code == 429


def test_admin_login_post_is_rate_limited(client, rate_limiting_on):
    codes = [
        client.post("/admin/login", data={"email": "x@example.com", "password": "nope"}).status_code
        for _ in range(15)
    ]
    assert 429 in codes, codes


def test_admin_login_get_not_limited(client, rate_limiting_on):
    # GET /admin/login (page load) must not be rate-limited — only POST attempts.
    codes = [client.get("/admin/login").status_code for _ in range(15)]
    assert all(c == 200 for c in codes), codes
