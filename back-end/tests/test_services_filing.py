"""Unit tests for the filing service, driven directly (no Flask).

These pin the behavior BEFORE the logic is extracted out of the route handlers,
so the extraction is provably behavior-preserving. Celery runs eagerly (autouse
fixture in conftest), so async_folder_delete actually runs inline here.
"""

import pytest

from tests import conftest_helpers as H


@pytest.fixture()
def services():
    """Import lazily so collection doesn't fail before the package exists."""
    from services import exceptions, filing_service

    return filing_service, exceptions


def test_delete_filing_dispatches_and_records_taskinfo(db_session, services):
    filing_service, _ = services
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, email="owner@example.com")
    folder = H.make_folder(s, org.id)
    folder_id = folder.id

    from database.models import celerytaskinfo
    from database.models import folder as folder_model

    task_id = filing_service.delete_filing(user_id=user.id, folderid=folder_id, session=s)

    # A Delete task-info row was recorded for this user's org.
    info = s.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).one()
    assert info.operation_type == "Delete"
    assert info.organization_id == org.id
    assert info.user_email == "owner@example.com"
    # Eager celery actually deleted the folder.
    assert s.query(folder_model).filter(folder_model.id == folder_id).first() is None


def test_delete_filing_wrong_org_raises(db_session, services):
    filing_service, exceptions = services
    s = db_session
    org_a = H.make_org(s, name="OrgA")
    folder_a = H.make_folder(s, org_a.id)
    org_b = H.make_org(s, name="OrgB")
    user_b = H.make_user(s, org_id=org_b.id, email="b@example.com")

    from database.models import folder as folder_model

    with pytest.raises(exceptions.ServiceError) as ei:
        filing_service.delete_filing(user_id=user_b.id, folderid=folder_a.id, session=s)
    assert ei.value.status == 400
    assert "organization" in ei.value.message.lower()
    # Folder A was NOT deleted.
    assert s.query(folder_model).filter(folder_model.id == folder_a.id).first() is not None


# --- filing status + windows (P4) -------------------------------------------


def test_mark_filed_and_reopen_roundtrip(db_session, services):
    filing_service, _ = services
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, email="filer@example.com")
    from datetime import date

    folder = H.make_folder(s, org.id, deadline=date(2026, 9, 1))

    assert folder.status == "open"
    filing_service.mark_filed(user_id=user.id, folderid=folder.id, session=s)
    assert folder.status == "filed" and folder.filed_at is not None

    filing_service.reopen(user_id=user.id, folderid=folder.id, session=s)
    assert folder.status == "open" and folder.filed_at is None


def test_mark_filed_wrong_org_raises(db_session, services):
    filing_service, exceptions = services
    s = db_session
    org = H.make_org(s, name="OrgA")
    other = H.make_org(s, name="OrgB", provider_id=999)
    outsider = H.make_user(s, org_id=other.id, email="outsider@example.com")
    folder = H.make_folder(s, org.id)

    import pytest as _pytest

    with _pytest.raises(exceptions.ServiceError):
        filing_service.mark_filed(user_id=outsider.id, folderid=folder.id, session=s)


def test_one_filing_per_org_per_window(db_session, services):
    filing_service, exceptions = services
    s = db_session
    org = H.make_org(s)
    from datetime import date

    # An existing June 2026 filing (deadline entered as the data-as-of date).
    H.make_folder(s, org.id, name="June filing", deadline=date(2026, 6, 30))

    import pytest as _pytest

    # The canonical due date classifies into the same window -> refused.
    with _pytest.raises(exceptions.ServiceError):
        filing_service.assert_window_available(org.id, date(2026, 9, 1), s)
    # A different window is fine.
    filing_service.assert_window_available(org.id, date(2026, 12, 31), s)


def test_switcher_data_labels_and_next_window(db_session, services):
    filing_service, _ = services
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, email="switch@example.com")
    from datetime import date

    june = H.make_folder(s, org.id, name="june", deadline=date(2026, 9, 1))
    filing_service.mark_filed(user_id=user.id, folderid=june.id, session=s)

    data = filing_service.switcher_data(user.id, s, today=date(2026, 6, 10))
    assert data["filings"][0]["label"] == "June 2026"
    assert data["filings"][0]["status"] == "filed"
    # June 2026 is the next window and a filing already exists for it.
    assert data["next_window"] is None

    # An org whose latest filing is December 2025 gets June 2026 announced.
    org2 = H.make_org(s, name="Org2", provider_id=42)
    user2 = H.make_user(s, org_id=org2.id, email="switch2@example.com")
    H.make_folder(s, org2.id, name="dec", deadline=date(2025, 12, 31))
    data2 = filing_service.switcher_data(user2.id, s, today=date(2026, 6, 10))
    assert data2["filings"][0]["label"] == "December 2025"
    assert data2["next_window"] == {"label": "June 2026", "due": "2026-09-01"}
