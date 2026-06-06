"""Shared helpers for the integration / e2e layers (Layer 2+).

Kept out of conftest.py so it's importable as a normal module (conftest is for
fixtures/hooks). These mirror the real pipeline (celery_tasks.process_data)
driven directly via the *_ops modules.
"""

import datetime
import json

from controllers.database_controller import (
    editfile_ops,
    fabric_ops,
    file_editfile_link_ops,
    file_ops,
    folder_ops,
    kml_ops,
    organization_ops,
    user_ops,
)
from database.models import kml_data

# Synthetic tech codes (see dev-data/synthetic/README.md)
TECH_WIRED = 50  # fiber -> wired
TECH_WIRELESS_UNLICENSED = 70  # wireless_total_dec2022
TECH_WIRELESS_LICENSED = 71  # wireless_25ghz_intersection


def make_org(session, name="TestOrg", provider_id=330054, brand_name="Acme"):
    org = organization_ops.create_organization(org_name=name, session=session)
    org.provider_id = provider_id
    org.brand_name = brand_name
    session.commit()
    return org


def make_folder(session, orgid, name="Filing", deadline=None, ftype="upload"):
    if deadline is None:
        deadline = datetime.date(2024, 5, 14)
    folder = folder_ops.create_folder(name, orgid, deadline, ftype, session)
    session.commit()
    return folder


def make_user(
    session, org_id=None, email="dev@example.com", password="Password123!", verified=True
):
    """Create a user, optionally attached to an org and marked verified."""
    res = user_ops.create_user_in_db(email, password, session)
    u = res["success"]
    u.verified = verified
    if org_id is not None:
        u.organization_id = org_id
    session.commit()
    return u


def seed_fabric(session, folderid, csv_bytes, filename="test_fabric.csv"):
    """Create a fabric file row and import its CSV into fabric_data (COPY)."""
    f = file_ops.create_file(
        filename=filename,
        content=csv_bytes,
        folderid=folderid,
        filetype="fabric",
        session=session,
    )
    session.commit()
    fabric_ops.write_to_db(f.id)
    return f


def seed_coverage(
    session,
    folderid,
    geo_bytes,
    filename,
    filetype,  # "wired" | "wireless"
    techType,
    maxDownloadSpeed=100,
    maxUploadSpeed=20,
    latency=1,
    category="R",
):
    f = file_ops.create_file(
        filename=filename,
        content=geo_bytes,
        folderid=folderid,
        filetype=filetype,
        maxDownloadSpeed=maxDownloadSpeed,
        maxUploadSpeed=maxUploadSpeed,
        techType=techType,
        latency=latency,
        category=category,
        session=session,
    )
    session.commit()
    return f


def compute_coverage(session, folderid, cov_file):
    """Run the real coverage computation for one coverage file (mirrors
    process_data's per-file step)."""
    network_type = 0 if cov_file.type == "wired" else 1
    kml_ops.add_network_data(
        folderid,
        cov_file.id,
        cov_file.maxDownloadSpeed,
        cov_file.maxUploadSpeed,
        cov_file.techType,
        network_type,
        cov_file.latency,
        cov_file.category,
        session,
    )
    session.commit()


def served_locations_for_file(session, file_id):
    """Set of location_ids that the pipeline marked served for a coverage file."""
    rows = session.query(kml_data.location_id).filter(kml_data.file_id == file_id).all()
    return {r[0] for r in rows}


def link_polygon_editfiles(session, folderid, cov_file, polygon_features):
    """Create one editfile per Polygon Feature and link it to the coverage file
    (this is how non-service edits are applied). `polygon_features` is a list of
    GeoJSON Feature dicts each with geometry.type == 'Polygon'."""
    created = []
    for i, feat in enumerate(polygon_features):
        ef = editfile_ops.create_editfile(
            filename=f"nonservice_{cov_file.id}_{i}",
            content=json.dumps(feat).encode("utf-8"),
            folderid=folderid,
            session=session,
        )
        session.commit()
        file_editfile_link_ops.link_file_and_editfile(cov_file.id, ef.id, session)
        created.append(ef)
    return created
