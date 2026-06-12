"""Service plans (services/plan_service.py) — unit tests, no Flask.

Pins the plan model: one default per tech per filing, write-through
to the legacy file columns (so the compute/export pipeline is untouched),
resolution precedence (file assignment > tech default > legacy columns), brand
resolution, legacy synthesis, and carry-forward via folder.copy().
"""

from datetime import date

import pytest

from services.exceptions import ServiceError
from tests import conftest_helpers as H


def _plan_svc():
    from services import plan_service

    return plan_service


def _make_coverage_file(s, folderid, name="cov.kml", tech=50, down=100, up=100):
    from database.models import file as file_model

    f = file_model(
        name=name,
        folder_id=folderid,
        type="kml",
        maxDownloadSpeed=down,
        maxUploadSpeed=up,
        techType=tech,
        latency=1,
        category="X",
    )
    s.add(f)
    s.commit()
    return f


def test_default_uniqueness_per_tech(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id, deadline=date(2026, 9, 1))

    p1 = svc.save_plan(folder.id, "Gig Fiber", 50, 1000, 1000, s, is_default=True)
    p2 = svc.save_plan(folder.id, "Budget Fiber", 50, 100, 100, s, is_default=True)
    s.refresh(p1)
    assert p1.is_default is False and p2.is_default is True
    # A different tech's default is unaffected.
    p3 = svc.save_plan(folder.id, "AirLink", 70, 100, 20, s, is_default=True)
    s.refresh(p2)
    assert p2.is_default is True and p3.is_default is True


def test_validation_rejects_bad_input(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)

    with pytest.raises(ServiceError):  # tech code 0 (Other) is never offered
        svc.save_plan(folder.id, "Mystery", 0, 100, 100, s)
    with pytest.raises(ServiceError):
        svc.save_plan(folder.id, "Slow", 50, 0, 100, s)
    with pytest.raises(ServiceError):
        svc.save_plan(folder.id, "BadCat", 50, 100, 100, s, category="homes")


def test_assignment_writes_through_to_file_columns(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, down=10, up=10)

    plan = svc.save_plan(folder.id, "Gig Fiber", 50, 1000, 500, s, low_latency=False, category="R")
    svc.assign_plan_to_file(f.id, plan.id, s)
    s.refresh(f)
    assert (f.maxDownloadSpeed, f.maxUploadSpeed, f.latency, f.category) == (1000, 500, 0, "R")

    # Editing the plan propagates to its files.
    svc.save_plan(folder.id, "Gig Fiber", 50, 2000, 2000, s, low_latency=True, plan_id=plan.id)
    s.refresh(f)
    assert (f.maxDownloadSpeed, f.maxUploadSpeed, f.latency) == (2000, 2000, 1)


def test_assignment_rejects_cross_tech(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, tech=70)
    fiber = svc.save_plan(folder.id, "Gig Fiber", 50, 1000, 1000, s)

    with pytest.raises(ServiceError):
        svc.assign_plan_to_file(f.id, fiber.id, s)


def _seed_kml_row(s, f, location_id=1001, down=0, up=0):
    from database.models import kml_data

    row = kml_data(
        location_id=location_id,
        served=True,
        file_id=f.id,
        longitude=-80.005,
        latitude=37.275,
        maxDownloadSpeed=down,
        maxUploadSpeed=up,
    )
    s.add(row)
    s.commit()
    return row


def test_default_plan_writes_through_to_unassigned_files(db_session):
    """REGRESSION: uploads carry 0/0 speeds — plans own the
    numbers. A DEFAULT plan governs every unassigned file of its tech, so
    saving one must stamp those files AND their computed kml rows without an
    explicit assignment; the export reads kml_data, so default-governed
    locations were shipping 0/0."""
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, down=0, up=0)
    row = _seed_kml_row(s, f)

    svc.save_plan(folder.id, "Gig Fiber", 50, 1000, 500, s, is_default=True)
    s.refresh(f)
    s.refresh(row)
    assert (f.maxDownloadSpeed, f.maxUploadSpeed) == (1000, 500)
    assert (row.maxDownloadSpeed, row.maxUploadSpeed) == (1000, 500)

    # A different tech's file is untouched...
    other = _make_coverage_file(s, folder.id, name="sector.geojson", tech=70, down=0, up=0)
    svc.save_plan(folder.id, "Gig Fiber", 50, 2000, 2000, s, plan_id=None, is_default=True)
    s.refresh(other)
    assert other.maxDownloadSpeed == 0
    # ...and so is a file explicitly assigned to a non-default plan.
    extra = svc.save_plan(folder.id, "Budget", 50, 100, 100, s)
    svc.assign_plan_to_file(f.id, extra.id, s)
    svc.save_plan(folder.id, "Gig Fiber+", 50, 3000, 3000, s, plan_id=None, is_default=True)
    s.refresh(f)
    assert f.maxDownloadSpeed == 100  # the assignment, not the new default


def test_unassigning_a_plan_falls_back_to_the_default(db_session):
    """Clearing a file's plan re-stamps the tech default (the plan that now
    governs it), not whatever the old assignment left behind."""
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, down=0, up=0)
    row = _seed_kml_row(s, f)
    svc.save_plan(folder.id, "Default Fiber", 50, 300, 300, s, is_default=True)
    extra = svc.save_plan(folder.id, "Budget", 50, 100, 100, s)
    svc.assign_plan_to_file(f.id, extra.id, s)
    s.refresh(row)
    assert row.maxDownloadSpeed == 100

    svc.assign_plan_to_file(f.id, None, s)
    s.refresh(f)
    s.refresh(row)
    assert f.plan_id is None
    assert (f.maxDownloadSpeed, row.maxDownloadSpeed) == (300, 300)


def test_plan_write_through_respects_area_edit_overrides(db_session):
    """Editing the governing plan re-stamps the file's kml rows — but a
    location whose plan an AREA EDIT set keeps the marker's plan (most
    specific wins: area edit > file assignment > tech default)."""
    from controllers.database_controller import editfile_ops, file_editfile_link_ops

    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, down=0, up=0)
    plain = _seed_kml_row(s, f, location_id=1001)
    overridden = _seed_kml_row(s, f, location_id=1002)
    default = svc.save_plan(folder.id, "Default Fiber", 50, 300, 300, s, is_default=True)
    marker_plan = svc.save_plan(folder.id, "Area Special", 50, 50, 50, s)

    ef = editfile_ops.create_editfile(
        filename="edit_area",
        content=b'{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[]}}',
        folderid=folder.id,
        session=s,
        markers=[{"id": 1002, "editedFile": [f.name], "plan_id": marker_plan.id}],
    )
    s.commit()  # flush the editfile id before linking (no autoflush)
    file_editfile_link_ops.link_file_and_editfile(f.id, ef.id, s)
    from controllers.database_controller import kml_ops

    kml_ops.reapply_plan_markers(f, s)
    s.commit()
    s.refresh(overridden)
    assert overridden.maxDownloadSpeed == 50

    # Editing the default re-stamps 1001 but must NOT clobber 1002.
    svc.save_plan(folder.id, "Default Fiber", 50, 999, 999, s, plan_id=default.id, is_default=True)
    s.refresh(plain)
    s.refresh(overridden)
    assert plain.maxDownloadSpeed == 999
    assert overridden.maxDownloadSpeed == 50


def test_restamp_folder_heals_pre_writethrough_data(db_session):
    """REGRESSION: filings whose plans were saved BEFORE default write-through
    existed still carry 0/0 in file columns and kml rows (write-through only
    fires on plan mutations). restamp_folder re-derives everything from the
    governing plans — and an area-edit plan marker still wins."""
    from controllers.database_controller import editfile_ops, file_editfile_link_ops, kml_ops
    from database.models import service_plan

    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, down=0, up=0)
    plain = _seed_kml_row(s, f, location_id=1001)
    overridden = _seed_kml_row(s, f, location_id=1002)
    # Simulate a pre-fix plan: inserted directly, NO write-through ever ran.
    stale_default = service_plan(
        folder_id=folder.id,
        name="Gig Fiber",
        tech_code=50,
        max_download=1000,
        max_upload=1000,
        low_latency=True,
        category="X",
        is_default=True,
    )
    marker_plan = service_plan(
        folder_id=folder.id,
        name="Area Special",
        tech_code=50,
        max_download=50,
        max_upload=50,
        low_latency=True,
        category="X",
        is_default=False,
    )
    s.add_all([stale_default, marker_plan])
    s.commit()
    ef = editfile_ops.create_editfile(
        filename="edit_area",
        content=b'{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[]}}',
        folderid=folder.id,
        session=s,
        markers=[{"id": 1002, "editedFile": [f.name], "plan_id": marker_plan.id}],
    )
    s.commit()
    file_editfile_link_ops.link_file_and_editfile(f.id, ef.id, s)
    kml_ops.reapply_plan_markers(f, s)
    s.commit()
    s.refresh(plain)
    assert plain.maxDownloadSpeed == 0  # the stale pre-fix state

    svc.restamp_folder(folder.id, s)
    s.refresh(f)
    s.refresh(plain)
    s.refresh(overridden)
    assert (f.maxDownloadSpeed, f.maxUploadSpeed) == (1000, 1000)
    assert plain.maxDownloadSpeed == 1000
    assert overridden.maxDownloadSpeed == 50  # the marker override survives


def test_plan_name_is_optional_defaulting_to_tech_and_speeds(db_session):
    """A blank name self-names as '<Tech> <down>/<up>' (e.g. 'Fiber 100/10')."""
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)

    p = svc.save_plan(folder.id, "", 50, 100, 10, s)
    assert p.name == "Fiber 100/10"
    p2 = svc.save_plan(folder.id, None, 70, 25, 3, s)
    assert p2.name == "Unlicensed FW 25/3"
    # Editing with a blank name re-derives from the (possibly new) values.
    svc.save_plan(folder.id, "  ", 50, 200, 20, s, plan_id=p.id)
    s.refresh(p)
    assert p.name == "Fiber 200/20"


def test_changing_a_plans_tech_releases_mismatched_files(db_session):
    """Technology is an editable plan attribute: moving a plan to another tech
    releases its assignments on files of the old tech (they fall back to their
    legacy columns / tech default) — a file is never left pointing at a plan
    of a different technology (the invariant assign_plan_to_file enforces)."""
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, tech=50, down=10, up=10)
    plan = svc.save_plan(folder.id, "Gig", 50, 1000, 1000, s)
    svc.assign_plan_to_file(f.id, plan.id, s)
    s.refresh(f)
    assert f.plan_id == plan.id

    svc.save_plan(folder.id, "Gig", 40, 1000, 1000, s, plan_id=plan.id)
    s.refresh(f)
    assert f.plan_id is None
    # A same-tech edit keeps the assignment.
    cable = _make_coverage_file(s, folder.id, name="cable.kml", tech=40)
    svc.assign_plan_to_file(cable.id, plan.id, s)
    svc.save_plan(folder.id, "Gig+", 40, 2000, 2000, s, plan_id=plan.id)
    s.refresh(cable)
    assert cable.plan_id == plan.id


def test_resolution_precedence(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f = _make_coverage_file(s, folder.id, tech=50)

    assert svc.resolve_for_file(f, s) is None  # legacy: no plans at all

    default = svc.save_plan(folder.id, "Default Fiber", 50, 500, 500, s, is_default=True)
    assert svc.resolve_for_file(f, s).id == default.id  # tech default applies

    extra = svc.save_plan(folder.id, "Extra Fiber", 50, 100, 100, s)
    svc.assign_plan_to_file(f.id, extra.id, s)
    s.refresh(f)
    assert svc.resolve_for_file(f, s).id == extra.id  # assignment beats default


def test_brand_resolution(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s, name="Canyon Networks")
    folder = H.make_folder(s, org.id)

    plain = svc.save_plan(folder.id, "Gig", 50, 1000, 1000, s)
    branded = svc.save_plan(folder.id, "AirLink", 70, 100, 20, s, brand="CanyonAir")
    assert svc.brand_for(plain, org) == "Canyon Networks"
    assert svc.brand_for(branded, org) == "CanyonAir"
    assert svc.brand_for(None, org) == "Canyon Networks"


def test_synthesize_legacy_plans(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id)
    f1 = _make_coverage_file(s, folder.id, name="a.kml", tech=50, down=1000, up=1000)
    f2 = _make_coverage_file(s, folder.id, name="b.kml", tech=50, down=1000, up=1000)
    f3 = _make_coverage_file(s, folder.id, name="c.geojson", tech=70, down=100, up=20)

    created = svc.synthesize_legacy_plans(folder.id, s)
    assert len(created) == 2  # one per distinct tuple
    for f in (f1, f2, f3):
        s.refresh(f)
    assert f1.plan_id == f2.plan_id != f3.plan_id
    assert all(p.is_default for p in created)  # first per tech is the default
    # Idempotent.
    assert svc.synthesize_legacy_plans(folder.id, s) == []


def test_folder_copy_carries_plans(db_session):
    svc = _plan_svc()
    s = db_session
    org = H.make_org(s)
    folder = H.make_folder(s, org.id, deadline=date(2026, 9, 1))
    f = _make_coverage_file(s, folder.id)
    plan = svc.save_plan(folder.id, "Gig Fiber", 50, 1000, 1000, s, is_default=True)
    svc.assign_plan_to_file(f.id, plan.id, s)

    new_folder = folder.copy(s, export=False, name="copy", deadline=date(2026, 12, 31))
    s.commit()

    from database.models import service_plan

    copied = s.query(service_plan).filter(service_plan.folder_id == new_folder.id).all()
    assert len(copied) == 1 and copied[0].name == "Gig Fiber" and copied[0].is_default
    copied_file = [x for x in new_folder.files][0]
    assert copied_file.plan_id == copied[0].id
