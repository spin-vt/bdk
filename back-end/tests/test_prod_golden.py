"""Layer 4 — PROD golden: replay real production filings through the real
backend and assert the computed coverage EXACTLY matches what prod produced.

This is the real correctness oracle. The reference (`kml_data.csv`) is the output
a prior, human-verified BDK run actually wrote to the prod DB. Correctness =
the current pipeline, given the SAME inputs (fabric + coverage files + the exact
linked edits), produces the SAME served location_ids — per file. Equality, not
overlap.

Real data, skip-if-absent (the prod extract lives only under
dev-data/real-do-not-commit/ on specific machines), local-only and slow
(seeds ~85 MB fabric + large KMLs and recomputes per file). Marked `golden` so
it's deselected from the fast committable suite.
"""

import json
import os
from datetime import date

import pandas as pd
import pytest

from controllers.database_controller import (
    editfile_ops,
    file_editfile_link_ops,
    file_ops,
    folder_ops,
    kml_ops,
    organization_ops,
)
from database.models import kml_data
from tests.conftest import REAL_DIR

PROD = os.path.join(REAL_DIR, "prod-extract")


def _upload_folders():
    idx = os.path.join(PROD, "INDEX.json")
    if not os.path.isfile(idx):
        return []
    return [f["folder_id"] for f in json.load(open(idx))["folders"] if f["type"] == "upload"]


pytestmark = [
    pytest.mark.golden,
    pytest.mark.realdata,
    pytest.mark.skipif(not os.path.isdir(PROD), reason="prod extract not present"),
]


def _replay(session, fid):
    """Seed folder <fid>'s exact prod inputs + linked edits, run the real
    coverage pipeline, and return (manifest, prod_file_id -> seeded file id map,
    prod kml_data dataframe)."""
    d = os.path.join(PROD, str(fid))
    m = json.load(open(os.path.join(d, "manifest.json")))

    org = organization_ops.create_organization(org_name=f"org{fid}", session=session)
    org.provider_id = m["organization"]["provider_id"]
    org.brand_name = m["organization"]["brand_name"]
    session.commit()
    folder = folder_ops.create_folder(m["folder"]["name"][:50], org.id, date(2025, 1, 1), "upload", session)
    session.commit()

    idmap = {}
    for f in m["files"]:
        with open(os.path.join(d, "inputs", f["written_as"]), "rb") as fh:
            data = fh.read()
        nf = file_ops.create_file(
            filename=f["name"], content=data, folderid=folder.id, filetype=f["type"],
            maxDownloadSpeed=f.get("maxDownloadSpeed"), maxUploadSpeed=f.get("maxUploadSpeed"),
            techType=f.get("techType"), latency=f.get("latency"), category=f.get("category"),
            session=session,
        )
        session.commit()
        idmap[f["id"]] = nf.id

    for ef in m["editfiles"]:
        with open(os.path.join(d, "edits", ef["written_as"]), "rb") as fh:
            data = fh.read()
        nef = editfile_ops.create_editfile(filename=ef["name"], content=data, folderid=folder.id, session=session)
        session.commit()
        for pfid in ef.get("linked_file_ids") or []:
            if pfid in idmap:
                file_editfile_link_ops.link_file_and_editfile(idmap[pfid], nef.id, session)
        session.commit()

    for f in m["files"]:
        if f["type"] == "fabric":
            continue
        nt = 0 if f["type"] == "wired" else 1
        kml_ops.add_network_data(
            folder.id, idmap[f["id"]], f.get("maxDownloadSpeed"), f.get("maxUploadSpeed"),
            f.get("techType"), nt, f.get("latency"), f.get("category"), session,
        )
        session.commit()

    prod = pd.read_csv(os.path.join(d, "output", "kml_data.csv"))
    return m, idmap, prod


@pytest.mark.parametrize("fid", _upload_folders())
def test_prod_filing_exact_match(db_session, fid):
    s = db_session
    m, idmap, prod = _replay(s, fid)

    mismatches = []
    for f in m["files"]:
        if f["type"] == "fabric":
            continue
        bdk = {r[0] for r in s.query(kml_data.location_id).filter(kml_data.file_id == idmap[f["id"]]).all()}
        ref = set(prod[prod.file_id == f["id"]].location_id.astype(int))
        if bdk != ref:
            mismatches.append(
                {"file": f["name"], "bdk": len(bdk), "prod": len(ref),
                 "bdk_only": len(bdk - ref), "prod_only": len(ref - bdk)}
            )

    assert not mismatches, f"folder {fid}: kml_data does not exactly match prod:\n" + "\n".join(
        str(x) for x in mismatches
    )
