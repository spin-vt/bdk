"""The legacy upgrade data policy (scripts/legacy_data_policy.py): filings
from past windows get marked filed, open-window filings stay open, and every
upload filing gets plans synthesized from its files' legacy columns.
Idempotent. (Plan synthesis itself is pinned in test_services_plans.)"""

from datetime import date

from database.models import service_plan
from scripts.legacy_data_policy import main as run_policy
from tests import conftest_helpers as H


def test_policy_files_past_windows_and_synthesizes_plans(db_session, monkeypatch):
    s = db_session
    org = H.make_org(s)
    past = H.make_folder(s, org.id, name="old", deadline=date(2024, 9, 3))
    open_now = H.make_folder(s, org.id, name="current", deadline=date(2026, 9, 1))
    H.seed_coverage(s, past.id, b"x", "cov.kml", "wired", 50, maxDownloadSpeed=100)
    H.seed_coverage(s, open_now.id, b"x", "cov2.kml", "wired", 50, maxDownloadSpeed=200)
    s.commit()

    # The script opens its own Session; run against the test DB as-is.
    run_policy()
    s.expire_all()

    assert past.status == "filed" and past.filed_at is not None
    assert open_now.status == "open"
    plans = {p.folder_id: p for p in s.query(service_plan).all()}
    assert plans[past.id].max_download == 100 and plans[past.id].is_default
    assert plans[open_now.id].max_download == 200

    # Idempotent: a second run changes nothing.
    filed_at = past.filed_at
    run_policy()
    s.expire_all()
    assert past.filed_at == filed_at
    assert s.query(service_plan).count() == 2
