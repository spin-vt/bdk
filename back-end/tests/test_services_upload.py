"""Unit tests for the upload-dispatch service (no Flask).

These pin the validation branches of submit_data before the logic is extracted.
The dispatch/orchestration happy path (operation 2: create-from-scratch) is
already covered end-to-end through the real HTTP route by
test_api_smoke.test_create_and_list_filing (eager celery), so here we focus on
the validation rules, which raise before any celery dispatch.
"""

import json

import pytest

from tests import conftest_helpers as H


@pytest.fixture()
def upload():
    from services import exceptions, upload_service

    return upload_service, exceptions


def _fd(**kw):
    """A fileData JSON string as the frontend sends it."""
    return json.dumps(kw)


def _call(upload_service, session, user_id, file_data_list, **kw):
    raw_files = [("f", b"x") for _ in file_data_list] or [("f", b"x")]
    return upload_service.dispatch_upload(
        user_id=user_id,
        folderid=kw.get("folderid", -1),
        raw_files=raw_files,
        file_data_list=file_data_list,
        import_folder_raw=kw.get("import_folder_raw", "-1"),
        deadline_raw=kw.get("deadline_raw", "2024-05-14"),
        session=session,
    )


def test_bad_extension_raises(db_session, upload):
    upload_service, exc = upload
    with pytest.raises(exc.ServiceError) as ei:
        _call(upload_service, db_session, 1, [_fd(name="bad.txt")])
    assert ei.value.status == 400
    assert "extension" in ei.value.message.lower()


def test_bad_speeds_raises(db_session, upload):
    upload_service, exc = upload
    with pytest.raises(exc.ServiceError) as ei:
        _call(
            upload_service,
            db_session,
            1,
            [_fd(name="a.kml", downloadSpeed="fast", uploadSpeed="x", latency="1", techType="50")],
        )
    assert "download and upload speeds" in ei.value.message.lower()


def test_bad_latency_techtype_raises(db_session, upload):
    upload_service, exc = upload
    with pytest.raises(exc.ServiceError) as ei:
        _call(
            upload_service,
            db_session,
            1,
            [_fd(name="a.kml", downloadSpeed="100", uploadSpeed="20", latency="x", techType="y")],
        )
    assert "latency" in ei.value.message.lower()


def test_bad_json_raises(db_session, upload):
    upload_service, exc = upload
    with pytest.raises(exc.ServiceError) as ei:
        _call(upload_service, db_session, 1, ["{not valid json"])
    assert "json" in ei.value.message.lower()


def test_unverified_user_raises(db_session, upload):
    upload_service, exc = upload
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id, verified=False)
    with pytest.raises(exc.ServiceError) as ei:
        _call(upload_service, s, user.id, [_fd(name="a.csv")])
    assert "verify" in ei.value.message.lower()


def test_no_org_raises(db_session, upload):
    upload_service, exc = upload
    s = db_session
    user = H.make_user(s, org_id=None)
    with pytest.raises(exc.ServiceError) as ei:
        _call(upload_service, s, user.id, [_fd(name="a.csv")])
    assert "organization" in ei.value.message.lower()


def test_missing_deadline_raises(db_session, upload):
    upload_service, exc = upload
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id)
    with pytest.raises(exc.ServiceError) as ei:
        _call(upload_service, s, user.id, [_fd(name="a.csv")], folderid=-1, deadline_raw=None)
    assert "deadline" in ei.value.message.lower()


def test_invalid_deadline_format_raises(db_session, upload):
    upload_service, exc = upload
    s = db_session
    org = H.make_org(s)
    user = H.make_user(s, org_id=org.id)
    with pytest.raises(exc.ServiceError) as ei:
        _call(
            upload_service, s, user.id, [_fd(name="a.csv")], folderid=-1, deadline_raw="14-05-2024"
        )
    assert "invalid deadline format" in ei.value.message.lower()
