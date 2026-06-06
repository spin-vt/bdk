"""P1.4 — unit tests for the filing service, driven directly (no Flask).

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
