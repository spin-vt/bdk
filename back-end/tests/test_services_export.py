"""Unit tests for the export service (no Flask). Pin behavior before the
exportFiling handler logic is extracted."""

import io

import pytest

from tests import conftest_helpers as H


@pytest.fixture()
def services():
    from services import exceptions, export_service

    return export_service, exceptions


def test_export_filing_returns_csv_and_name(db_session, services):
    export_service, _ = services
    s = db_session
    org = H.make_org(s)  # provider_id=330054, brand_name="Acme"
    user = H.make_user(s, org_id=org.id)
    folder = H.make_folder(s, org.id)

    csv_output, download_name = export_service.export_filing(
        user_id=user.id, folderid=folder.id, session=s
    )
    assert isinstance(csv_output, io.BytesIO)
    assert "Acme" in download_name


def test_export_filing_invalid_id_raises(db_session, services):
    export_service, exceptions = services
    with pytest.raises(exceptions.ServiceError) as ei:
        export_service.export_filing(user_id=1, folderid=-1, session=db_session)
    assert ei.value.status == 400
    assert "invalid" in ei.value.message.lower()


def test_export_filing_wrong_org_raises(db_session, services):
    export_service, exceptions = services
    s = db_session
    org_a = H.make_org(s, name="OrgA")
    folder_a = H.make_folder(s, org_a.id)
    org_b = H.make_org(s, name="OrgB")
    user_b = H.make_user(s, org_id=org_b.id, email="b@example.com")

    with pytest.raises(exceptions.ServiceError) as ei:
        export_service.export_filing(user_id=user_b.id, folderid=folder_a.id, session=s)
    assert ei.value.status == 400
    assert "organization" in ei.value.message.lower()


def test_export_filing_missing_provider_brand_raises(db_session, services):
    export_service, exceptions = services
    s = db_session
    org = H.make_org(s, provider_id=None)  # no provider id
    user = H.make_user(s, org_id=org.id)
    folder = H.make_folder(s, org.id)

    with pytest.raises(exceptions.ServiceError) as ei:
        export_service.export_filing(user_id=user.id, folderid=folder.id, session=s)
    assert ei.value.status == 400
    assert "provider id" in ei.value.message.lower()
