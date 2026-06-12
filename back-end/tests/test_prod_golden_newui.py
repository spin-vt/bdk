"""Layer 4b — NEW-UI golden: replay the same real prod filings, but driven
through the REDESIGNED surfaces, and assert the export is identical.

The legacy golden (test_prod_golden) seeds files directly with per-file
speeds and computes — the pre-plans pipeline. This one drives what a user of
the new app does: fabric through the intake upload, coverage files through
the files-page upload (0/0 placeholder speeds — plans own the numbers), tech
corrections through the tech route, ONE DEFAULT PLAN PER TECH carrying the
prod per-file values, then a regenerate. Byte-identical output = the plans
write-through path reproduces exactly what the legacy per-file-speeds path
produced.

Two deliberate non-UI steps, both documented:
  - edits are seeded as editfiles + links (drawing needs a browser; the
    geometric edit semantics at compute are what we're pinning), with the
    recompute dispatched through the real /api/regenerate_map route;
  - the CSV is built by the shared kml_ops.export builder for BOTH filings
    (dispatch_copy=False — no snapshot copy), so the comparison isolates the
    pipeline, not the snapshot plumbing. Rows are compared as sorted lines:
    plan write-through UPDATEs relocate rows in Postgres, so physical row
    order is not part of the contract.

Real data, skip-if-absent, local-only, slow; marked `golden`.
"""

import io
import json
import os
from datetime import date

import pytest

from controllers.database_controller import (
    editfile_ops,
    file_editfile_link_ops,
    kml_ops,
)
from database.models import file as file_model
from database.models import kml_data
from tests import conftest_helpers as H
from tests.conftest_helpers import login_page_session
from tests.test_prod_golden import PROD, _replay, _upload_folders

pytestmark = [
    pytest.mark.golden,
    pytest.mark.realdata,
    pytest.mark.skipif(not os.path.isdir(PROD), reason="prod extract not present"),
]

DATE_FORMAT = "%Y-%m-%d"


@pytest.fixture()
def client(db_session):
    import routes  # noqa: F401
    from utils.flask_app import app

    app.config["TESTING"] = True
    with H.CsrfFlaskClient(app) as c:
        yield c


@pytest.fixture()
def no_tiles(monkeypatch):
    from controllers.celery_controller import celery_tasks as ct

    monkeypatch.setattr(ct, "_coalesced_tile_rebuild", lambda *a, **k: "stubbed")


def _get_user(session, email):
    from database.models import user as user_model

    return session.query(user_model).filter(user_model.email == email).one()


def _csv_bytes(session, folder, org):
    out = kml_ops.export(
        folder.id,
        org.provider_id,
        org.brand_name,
        folder.deadline.strftime(DATE_FORMAT),
        session,
        dispatch_copy=False,
    )
    return out.getvalue()


def _drive_new_ui(client, session, fid, manifest_dir, m):
    """Build the same filing the new-UI way; returns (org, folder)."""
    email = f"newui{fid}@example.com"
    login_page_session(client, email=email)
    org = H.make_org(session, name=f"newui-org{fid}")
    org.provider_id = m["organization"]["provider_id"]
    org.brand_name = m["organization"]["brand_name"]
    u = _get_user(session, email)
    u.organization_id = org.id
    u.verified = True
    session.commit()
    folder = H.make_folder(session, org.id, name=f"newui{fid}", deadline=date(2025, 1, 1))
    client.set_cookie("bdk_filing", str(folder.id))

    # 1. Fabric through the intake upload (vintage override: the extract's
    #    fabric predates this synthetic window).
    fabric = next(f for f in m["files"] if f["type"] == "fabric")
    with open(os.path.join(manifest_dir, "inputs", fabric["written_as"]), "rb") as fh:
        fabric_bytes = fh.read()
    resp = client.post(
        "/files/fabric/upload",
        data={"fabric_file": (io.BytesIO(fabric_bytes), fabric["name"]), "override": "1"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    # 2. Coverage files through the files-page upload (geometry guesses the
    #    tech; corrected through the tech route below).
    coverage = [f for f in m["files"] if f["type"] != "fabric"]
    uploads = []
    for f in coverage:
        with open(os.path.join(manifest_dir, "inputs", f["written_as"]), "rb") as fh:
            uploads.append((io.BytesIO(fh.read()), f["name"]))
    resp = client.post(
        "/files/coverage/upload",
        data={"network_files": uploads},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    session.expire_all()
    by_name = {
        x.name: x
        for x in session.query(file_model).filter(
            file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless"))
        )
    }
    assert set(by_name) == {f["name"] for f in coverage}

    # 3. Correct any guessed tech to the prod tech.
    for f in coverage:
        nf = by_name[f["name"]]
        if nf.techType != f["techType"]:
            resp = client.post(
                f"/files/coverage/{nf.id}/tech",
                data={"tech": str(f["techType"]), "confirm": "1"},
            )
            assert resp.status_code == 200

    # 4. Plans: one DEFAULT per tech for the tech's common values; any file
    #    with different values gets its own plan, explicitly assigned.
    by_tech = {}
    for f in coverage:
        key = (
            f["techType"],
            f["maxDownloadSpeed"],
            f["maxUploadSpeed"],
            f["latency"],
            f["category"],
        )
        by_tech.setdefault(f["techType"], {}).setdefault(key, []).append(f["name"])
    from database.models import service_plan

    for tech, variants in by_tech.items():
        # The most common variant becomes the tech default.
        ranked = sorted(variants.items(), key=lambda kv: -len(kv[1]))
        for i, (key, names) in enumerate(ranked):
            _, down, up, latency, category = key
            form = {
                "tech": str(tech),
                "name": "",  # autonames as "<Tech> <down>/<up>"
                "down": str(down),
                "up": str(up),
                "category": category if category else "X",
                "use_default_brand": "on",
                "return_tab": "plans",
            }
            if latency:
                form["low_latency"] = "on"
            if i == 0:
                form["is_default"] = "on"
            resp = client.post("/files/plans/save", data=form)
            assert resp.status_code == 200 and resp.headers.get("HX-Redirect"), resp.get_data(
                as_text=True
            )
            if i > 0:
                session.expire_all()
                plan = (
                    session.query(service_plan)
                    .filter_by(folder_id=folder.id, tech_code=tech)
                    .order_by(service_plan.id.desc())
                    .first()
                )
                for name in names:
                    resp = client.post(
                        f"/files/coverage/{by_name[name].id}/plan",
                        data={"plan_id": str(plan.id)},
                    )
                    assert resp.status_code == 200

    # 5. The prod filing's edits (geometric editfiles + links — drawing needs
    #    a browser), then the real regenerate to re-derive coverage with them.
    idmap = {}
    for f in coverage:
        idmap[f["id"]] = by_name[f["name"]].id
    for ef in m["editfiles"]:
        with open(os.path.join(manifest_dir, "edits", ef["written_as"]), "rb") as fh:
            data = fh.read()
        nef = editfile_ops.create_editfile(
            filename=ef["name"], content=data, folderid=folder.id, session=session
        )
        session.commit()
        for pfid in ef.get("linked_file_ids") or []:
            if pfid in idmap:
                file_editfile_link_ops.link_file_and_editfile(idmap[pfid], nef.id, session)
        session.commit()
    if m["editfiles"]:
        resp = client.post("/api/regenerate_map", json={"folderID": folder.id})
        assert resp.status_code == 200, resp.get_data(as_text=True)
    session.expire_all()
    return org, folder


@pytest.mark.parametrize("fid", _upload_folders())
def test_new_ui_filing_exports_identically(client, db_session, no_tiles, fid):
    s = db_session
    d = os.path.join(PROD, str(fid))
    m = json.load(open(os.path.join(d, "manifest.json")))

    # Reference: the legacy replay (validated against prod output by the
    # legacy golden) and its CSV.
    m_ref, idmap_ref, prod = _replay(s, fid)
    from database.models import folder as folder_model
    from database.models import organization as org_model

    ref_org = s.query(org_model).filter(org_model.name == f"org{fid}").one()
    ref_folder = s.query(folder_model).filter(folder_model.organization_id == ref_org.id).one()
    ref_csv = _csv_bytes(s, ref_folder, ref_org)

    # The same filing, built the new-UI way.
    org, folder = _drive_new_ui(client, s, fid, d, m)

    # Per-file served sets must equal the PROD reference exactly.
    by_name = {
        x.name: x
        for x in s.query(file_model).filter(
            file_model.folder_id == folder.id, file_model.type.in_(("wired", "wireless"))
        )
    }
    mismatches = []
    for f in m["files"]:
        if f["type"] == "fabric":
            continue
        bdk = {
            r[0]
            for r in s.query(kml_data.location_id)
            .filter(kml_data.file_id == by_name[f["name"]].id)
            .all()
        }
        ref = set(prod[prod.file_id == f["id"]].location_id.astype(int))
        if bdk != ref:
            mismatches.append(
                {
                    "file": f["name"],
                    "bdk": len(bdk),
                    "prod": len(ref),
                    "bdk_only": len(bdk - ref),
                    "prod_only": len(ref - bdk),
                }
            )
    assert not mismatches, f"folder {fid}: new-UI kml_data diverges from prod:\n" + "\n".join(
        str(x) for x in mismatches
    )

    # The export CSV must be IDENTICAL to the legacy path's (sorted lines —
    # physical row order is not part of the contract).
    new_csv = _csv_bytes(s, folder, org)
    ref_lines = ref_csv.splitlines()
    new_lines = new_csv.splitlines()
    assert ref_lines[0] == new_lines[0]  # header
    assert len(ref_lines) == len(new_lines)
    assert sorted(ref_lines[1:]) == sorted(new_lines[1:])
