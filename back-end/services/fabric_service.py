"""Fabric intake v2 — the CostQuest delivery as the unit of work.

Accepts the delivery zip or an individual CSV, classifies the parts
(active / non_bsl / supplemental — see services/fabric_intake.py and
back-end/docs/bdc-fabric-format.md), checks the vintage against the filing's window
(hard warning, overridable), and dispatches ingestion:

  - a delivery containing an *active* file replaces same-role predecessors and
    runs the full operation-4 recompute (kml_data wiped + recomputed against
    the new fabric, existing edits re-applied exactly via their markers, tiles
    rebuilt) — the same proven chain a file deletion uses;
  - a non_bsl/supplemental-only delivery just ingests (those roles never feed
    coverage computation), no recompute, no retile.

Also serves the fabric status card (files + vintage + stats) and the
fabric-powered address search (fabric + supplemental, served/BSL flags — no
external geocoding, per the product rules).
"""

import io
import zipfile

from celery import chain
from sqlalchemy import distinct, func

from controllers.database_controller import (
    celerytaskinfo_ops,
    file_ops,
    folder_ops,
    user_ops,
)
from database.models import fabric_data, kml_data, supplemental_data
from services import fabric_intake
from services.audit import log_action
from services.exceptions import ServiceError

ROLE_TO_TYPE = {
    fabric_intake.ROLE_ACTIVE: "fabric",
    fabric_intake.ROLE_NON_BSL: "fabric_non_bsl",
    fabric_intake.ROLE_SUPPLEMENTAL: "fabric_supplemental",
}
TYPE_TO_ROLE = {v: k for k, v in ROLE_TO_TYPE.items()}

# file.type values whose rows live in fabric_data (drive the map + stats).
_POINT_TYPES = ("fabric", "fabric_non_bsl")


def _is_true(bsl_flag):
    return (bsl_flag or "").strip().upper() in ("TRUE", "T", "1")


def _vintage_dict(check):
    return {
        "matches": check.matches,
        "expected_version": check.expected_version,
        "expected_label": check.expected_label,
        "got_version": check.got_version,
    }


def _owned_folder(user_id, folderid, session):
    if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)
    return folder_ops.get_folder_with_id(folderid=folderid, session=session)


def intake_fabric(user_id, folderid, filename, data, session, override_vintage=False):
    """Validate + classify a fabric upload, create the file rows (with their
    vintage), and dispatch the ingestion chain. Returns a summary dict with
    the celery task id. Raises ServiceError(409) on a vintage mismatch unless
    override_vintage is set."""
    user = user_ops.get_user_with_id(user_id, session=session)
    if not user.verified:
        raise ServiceError("Please Verify your email to start working on a filing", 400)
    if not user.organization_id:
        raise ServiceError("Create or join an organization to start working on a filing", 400)

    folder = _owned_folder(user_id, folderid, session)
    if folder.type != "upload":
        raise ServiceError("Fabric can only be added to a filing, not a generated submission", 400)
    if folder.status == "filed":
        raise ServiceError(
            "This filing is marked as filed — reopen it before changing its fabric", 409
        )

    parts, unrecognized = fabric_intake.inspect_upload(filename, data)
    if not parts:
        raise ServiceError(
            "This doesn't look like a CostQuest fabric delivery — no Active BSL, "
            "Active NoBSL, or Supplemental CSV was recognized",
            400,
        )
    roles = [p.role for p in parts]
    if len(set(roles)) != len(roles):
        raise ServiceError("The delivery contains more than one file for the same fabric role", 400)

    # The active file's vintage speaks for the delivery (the real zips are
    # uniform); a delivery without an active part is checked off its first part.
    primary = next((p for p in parts if p.role == fabric_intake.ROLE_ACTIVE), parts[0])
    check = fabric_intake.check_vintage(primary.data_as_of, folder.deadline)
    if not check.matches and not override_vintage:
        got = (
            f"data as of {primary.data_as_of:%B %d, %Y} (fabric version {check.got_version})"
            if check.got_version
            else "of an unrecognizable vintage"
        )
        raise ServiceError(
            f"This fabric is {got}, but the {check.expected_label} filing expects fabric "
            f"version {check.expected_version}. Location IDs may not line up across versions — "
            "use the right vintage, or override to continue with this one.",
            409,
        )

    # Same-role predecessors get replaced (deleted in the dispatched chain).
    replaced_ids, replaced_names = [], []
    for part in parts:
        for old in file_ops.get_files_by_type(folderid, ROLE_TO_TYPE[part.role], session):
            replaced_ids.append(old.id)
            replaced_names.append(old.name)

    is_zip = filename.lower().endswith(".zip") or data[:4] == b"PK\x03\x04"
    zf = zipfile.ZipFile(io.BytesIO(data)) if is_zip else None
    new_files = []
    for part in parts:
        content = zf.read(part.member) if zf else data
        new_file = file_ops.create_file(
            filename=part.member.rsplit("/", 1)[-1],
            content=content,
            folderid=folderid,
            filetype=ROLE_TO_TYPE[part.role],
            session=session,
        )
        new_file.fabric_data_as_of = part.data_as_of
        new_file.fabric_release = part.release
        new_files.append(new_file)
    session.commit()

    # Deferred import: celery_tasks imports controller modules that import
    # services, so a module-level import here would be a cycle.
    from controllers.celery_controller.celery_tasks import (
        async_delete_files,
        import_fabric_data,
        process_data,
    )

    if any(p.role == fabric_intake.ROLE_ACTIVE for p in parts):
        # New/replaced active fabric: full recompute (operation 4) — wipes
        # kml_data, recomputes against the new fabric, re-applies edits via
        # their markers, rebuilds tiles.
        ingest = process_data.si(folderid=folderid, operation=4)
    else:
        # non_bsl / supplemental never feed computation: ingest only.
        ingest = import_fabric_data.si(folderid=folderid)
    result = chain(
        async_delete_files.s(file_ids=replaced_ids, editfile_ids=[]), ingest
    ).apply_async()

    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Fabric",
        operation_detail="Replace the fabric" if replaced_ids else "Add the fabric",
        user_email=user.email,
        organization_id=user.organization_id,
        folder_deadline=folder.deadline,
        session=session,
        files_changed=", ".join(f.name for f in new_files),
    )

    log_action(
        "upload",
        user_id=user.id,
        resource_type="folder",
        resource_id=folderid,
        details={"kind": "fabric", "task_id": result.id, "files": [f.name for f in new_files]},
    )
    return {
        "task_id": result.id,
        "roles": roles,
        "files": [f.name for f in new_files],
        "replaced": replaced_names,
        "vintage": _vintage_dict(check),
        "unrecognized": unrecognized,
    }


def fabric_vintage_warning(folderid, session):
    """The warn-everywhere signal: a vintage dict when the filing's active
    fabric carries a KNOWN version its window doesn't expect, else None.
    Wrong-vintage filings are allowed (override at upload) — this drives the
    loud chips/confirms, so an unknown vintage (legacy fabrics with no
    data-as-of) deliberately stays quiet."""
    from database.models import file as file_model

    folder = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    if folder is None:
        return None
    active = (
        session.query(file_model)
        .filter(file_model.folder_id == folderid, file_model.type == "fabric")
        .first()
    )
    if active is None or active.fabric_data_as_of is None:
        return None
    check = fabric_intake.check_vintage(active.fabric_data_as_of, folder.deadline)
    if check.matches or check.got_version is None:
        return None
    return _vintage_dict(check)


def fabric_status(user_id, folderid, session):
    """The fabric card: per-role file info (with vintage), the vintage check
    against the filing window, and the stat blocks."""
    folder = _owned_folder(user_id, folderid, session)

    files = [f for f in folder.files if f.type in TYPE_TO_ROLE]
    active_file = None
    files_out = []
    for f in files:
        role = TYPE_TO_ROLE[f.type]
        if role == fabric_intake.ROLE_ACTIVE:
            active_file = f
        files_out.append(
            {
                "id": f.id,
                "name": f.name,
                "role": role,
                "data_as_of": f.fabric_data_as_of.isoformat() if f.fabric_data_as_of else None,
                "release": f.fabric_release,
                "version": fabric_intake.version_for_data_as_of(f.fabric_data_as_of),
                "computed": bool(f.computed),
            }
        )

    vintage = None
    if active_file is not None:
        vintage = _vintage_dict(
            fabric_intake.check_vintage(active_file.fabric_data_as_of, folder.deadline)
        )

    point_ids = [f.id for f in files if f.type in _POINT_TYPES]
    active_ids = [f.id for f in files if f.type == "fabric"]
    supp_ids = [f.id for f in files if f.type == "fabric_supplemental"]

    def _count(expr, file_ids):
        if not file_ids:
            return 0
        return (
            session.query(func.count(distinct(expr)))
            .filter(fabric_data.file_id.in_(file_ids))
            .scalar()
            or 0
        )

    stats = {
        "locations": _count(fabric_data.location_id, point_ids),
        "bsl_locations": _count(fabric_data.location_id, active_ids),
        # country_geoid is the model's (pre-existing) typo for county_geoid.
        "counties": _count(fabric_data.country_geoid, point_ids),
        "states": _count(fabric_data.state, point_ids),
        "supplemental_addresses": (
            session.query(func.count(supplemental_data.id))
            .filter(supplemental_data.file_id.in_(supp_ids))
            .scalar()
            or 0
        )
        if supp_ids
        else 0,
    }

    return {"files": files_out, "vintage": vintage, "stats": stats}


def search_addresses(user_id, folderid, query, session, limit=10):
    """Autocomplete over the fabric (+ supplemental addresses), fabric-powered
    only. Every hit carries served (any coverage file serves the location) and
    bsl flags; supplemental hits inherit the location's coordinates."""
    folder = _owned_folder(user_id, folderid, session)
    tokens = (query or "").split()
    if not tokens:
        return []

    files = folder.files
    point_ids = [f.id for f in files if f.type in _POINT_TYPES]
    supp_ids = [f.id for f in files if f.type == "fabric_supplemental"]
    coverage_ids = [f.id for f in files if f.name.endswith((".kml", ".geojson"))]
    if not point_ids:
        return []  # no fabric yet — the soft empty state

    def _token_filters(*cols):
        haystack = func.lower(func.concat_ws(" ", *cols))
        return [haystack.like(f"%{t.lower()}%") for t in tokens]

    results = {}  # (location_id, address) -> hit, insertion-ordered

    fabric_rows = (
        session.query(fabric_data)
        .filter(
            fabric_data.file_id.in_(point_ids),
            *_token_filters(
                fabric_data.address_primary,
                fabric_data.city,
                fabric_data.state,
                fabric_data.zip_code,
            ),
        )
        .order_by(fabric_data.address_primary)
        .limit(limit)
        .all()
    )
    for r in fabric_rows:
        results[(r.location_id, r.address_primary)] = {
            "location_id": r.location_id,
            "address": r.address_primary,
            "city": r.city,
            "state": r.state,
            "zip": r.zip_code,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "bsl": _is_true(r.bsl_flag),
            "source": "fabric",
        }

    if supp_ids and len(results) < limit:
        supp_rows = (
            session.query(supplemental_data)
            .filter(
                supplemental_data.file_id.in_(supp_ids),
                *_token_filters(
                    supplemental_data.address,
                    supplemental_data.city,
                    supplemental_data.state,
                    supplemental_data.zip_code,
                ),
            )
            .order_by(supplemental_data.address)
            .limit(limit)
            .all()
        )
        loc_ids = {r.location_id for r in supp_rows}
        fabric_by_loc = {
            f.location_id: f
            for f in session.query(fabric_data).filter(
                fabric_data.file_id.in_(point_ids), fabric_data.location_id.in_(loc_ids)
            )
        }
        for r in supp_rows:
            home = fabric_by_loc.get(r.location_id)
            key = (r.location_id, r.address)
            if key in results:
                continue
            if home is not None and r.address == home.address_primary:
                continue  # the P row mirrors the fabric's primary address
            results[key] = {
                "location_id": r.location_id,
                "address": r.address,
                "city": r.city,
                "state": r.state,
                "zip": r.zip_code,
                "latitude": home.latitude if home else None,
                "longitude": home.longitude if home else None,
                "bsl": _is_true(home.bsl_flag) if home else False,
                "source": "supplemental",
            }

    hits = list(results.values())[:limit]
    served = set()
    if coverage_ids and hits:
        served = {
            row[0]
            for row in session.query(distinct(kml_data.location_id)).filter(
                kml_data.file_id.in_(coverage_ids),
                kml_data.location_id.in_({h["location_id"] for h in hits}),
                kml_data.served.is_(True),
            )
        }
    for h in hits:
        h["served"] = h["location_id"] in served
    return hits
