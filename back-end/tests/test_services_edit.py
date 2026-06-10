"""Unit tests for the edit-apply service (no Flask). The dispatched celery
chain (DB apply + the heavy retile pipeline) is stubbed so we test the
service's validation/orchestration, not tippecanoe; the chain itself is
covered in test_tiles_split.py."""

import pytest

from tests import conftest_helpers as H


class _FakeResult:
    task_id = "fake-edit-task"


class _FakeChain:
    def apply_async(self, *a, **k):
        return _FakeResult()


@pytest.fixture()
def edit_service(monkeypatch):
    from services import edit_service as mod

    monkeypatch.setattr(mod, "chain", lambda *sigs: _FakeChain())
    return mod


@pytest.fixture()
def errors():
    from services import exceptions

    return exceptions


def _markers(*editedfile_lists):
    """One polygon of points, each point carrying the given editedFile list."""
    return [[{"editedFile": ef} for ef in editedfile_lists]]


def test_apply_edit_dispatches_and_records(db_session, edit_service):
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, email="owner@example.com")
    folder = H.make_folder(s, org.id)

    from database.models import celerytaskinfo

    task_id = edit_service.apply_edit(
        user_id=user.id,
        folderid=folder.id,
        markers=_markers(["a.kml"], [], ["b.kml"]),
        polygonfeatures=[],
        session=s,
    )
    assert task_id == "fake-edit-task"
    info = s.query(celerytaskinfo).filter(celerytaskinfo.task_id == task_id).one()
    assert info.operation_type == "Edit"
    assert info.organization_id == org.id
    assert info.files_changed == "a.kml, b.kml"  # sorted union of editedFile names


def test_apply_edit_invalid_folder_raises(db_session, edit_service, errors):
    with pytest.raises(errors.ServiceError) as ei:
        edit_service.apply_edit(
            user_id=1,
            folderid=-1,
            markers=_markers(["a.kml"]),
            polygonfeatures=[],
            session=db_session,
        )
    assert ei.value.status == 400
    assert "folder id" in ei.value.message.lower()


def test_apply_edit_unverified_raises(db_session, edit_service, errors):
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, verified=False)
    folder = H.make_folder(s, org.id)
    with pytest.raises(errors.ServiceError) as ei:
        edit_service.apply_edit(
            user_id=user.id,
            folderid=folder.id,
            markers=_markers(["a.kml"]),
            polygonfeatures=[],
            session=s,
        )
    assert "verify" in ei.value.message.lower()


def test_apply_edit_no_org_raises(db_session, edit_service, errors):
    s = db_session
    user = H.make_user(s, org_id=None)  # no organization
    with pytest.raises(errors.ServiceError) as ei:
        edit_service.apply_edit(
            user_id=user.id, folderid=1, markers=_markers(["a.kml"]), polygonfeatures=[], session=s
        )
    assert "organization" in ei.value.message.lower()


def test_apply_edit_wrong_org_raises(db_session, edit_service, errors):
    s = db_session
    org_a = H.make_org(s, name="OrgA")
    folder_a = H.make_folder(s, org_a.id)
    org_b = H.make_org(s, name="OrgB")
    user_b = H.make_user(s, org_id=org_b.id, email="b@example.com")
    with pytest.raises(errors.ServiceError) as ei:
        edit_service.apply_edit(
            user_id=user_b.id,
            folderid=folder_a.id,
            markers=_markers(["a.kml"]),
            polygonfeatures=[],
            session=s,
        )
    assert "organization" in ei.value.message.lower()


def test_apply_edit_no_valid_edits_raises(db_session, edit_service, errors):
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id)
    folder = H.make_folder(s, org.id)
    with pytest.raises(errors.ServiceError) as ei:
        edit_service.apply_edit(
            user_id=user.id,
            folderid=folder.id,
            markers=_markers([], []),  # all points have empty editedFile
            polygonfeatures=[],
            session=s,
        )
    assert "no valid edits" in ei.value.message.lower()
