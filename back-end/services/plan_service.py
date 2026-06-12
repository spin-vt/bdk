"""Service plans: create/update, file assignment, resolution, brand, legacy
synthesis.

Plans are the source of truth for advertised speeds/latency/category, but they
work by WRITE-THROUGH: assigning or editing a plan stamps its values onto the
assigned files' legacy columns (maxDownloadSpeed/maxUploadSpeed/latency/
category), which is what the coverage compute stamps into kml_data and the
export CSV reads. The pipeline is untouched; a file with no plan behaves
exactly as before (golden-guarded).

Resolution precedence (most specific wins): area edit > file assignment >
tech default. Area-edit plans land with the studio map page; this module
resolves the file/default levels.

No tech code 0 (Other) — deliberately not offered anywhere.
"""

from database.models import file as file_model
from database.models import kml_data, service_plan
from services.exceptions import ServiceError

# BDC business_residential_code values (the design's category select).
CATEGORY_LABELS = {
    "X": "Residential + Business",
    "R": "Residential only",
    "B": "Business only",
}

# Geometry-derived technology groups (design rule: lines -> wired, polygons ->
# fixed wireless; tech code 0 deliberately omitted).
WIRED_TECHS = {50: "Fiber", 40: "Cable", 10: "DSL"}
WIRELESS_TECHS = {70: "Unlicensed FW", 71: "Licensed FW", 72: "LBR FW"}
TECH_NAMES = {**WIRED_TECHS, **WIRELESS_TECHS}


def _validate(name, tech_code, max_download, max_upload, category):
    if tech_code not in TECH_NAMES:
        raise ServiceError(f"Unknown technology code {tech_code}", 400)
    if category not in CATEGORY_LABELS:
        raise ServiceError("Category must be one of X, R, B", 400)
    try:
        if int(max_download) <= 0 or int(max_upload) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ServiceError("Speeds must be positive integers", 400) from None


def _write_through(plan, session):
    """Stamp the plan's values onto every file it GOVERNS: explicit
    assignments, plus — for a default plan — every unassigned file of its
    tech (uploads carry 0/0 placeholder speeds; plans own the
    numbers, so default-governed files must be stamped too or the export
    ships zeros). Files that are ALREADY computed have their kml_data rows
    stamped as well — the export reads kml_data, so a plan saved after the
    compute must reach it without waiting for a recompute. Area-edit plan
    markers are re-applied AFTER the stamp, so the most-specific-wins
    precedence (area edit > assignment > default) survives a plan edit."""
    from controllers.database_controller import kml_ops

    files = session.query(file_model).filter(file_model.plan_id == plan.id).all()
    if plan.is_default:
        files += (
            session.query(file_model)
            .filter(
                file_model.folder_id == plan.folder_id,
                file_model.plan_id.is_(None),
                file_model.techType == plan.tech_code,
            )
            .all()
        )
    for f in files:
        f.maxDownloadSpeed = plan.max_download
        f.maxUploadSpeed = plan.max_upload
        f.latency = 1 if plan.low_latency else 0
        f.category = plan.category
        session.query(kml_data).filter(kml_data.file_id == f.id).update(
            {
                kml_data.maxDownloadSpeed: plan.max_download,
                kml_data.maxUploadSpeed: plan.max_upload,
                kml_data.latency: 1 if plan.low_latency else 0,
                kml_data.category: plan.category,
            }
        )
        kml_ops.reapply_plan_markers(f, session)


def save_plan(
    folder_id,
    name,
    tech_code,
    max_download,
    max_upload,
    session,
    low_latency=True,
    category="X",
    brand=None,
    is_default=False,
    plan_id=None,
):
    """Create or update a plan. The name is optional — left blank it
    self-names as "<Tech> <down>/<up>" (e.g. "Fiber 100/10"). Setting
    is_default clears the previous default for the same (folder, tech).
    Updates write through to assigned files. Returns the plan."""
    _validate(name, tech_code, max_download, max_upload, category)
    name = (name or "").strip() or f"{TECH_NAMES[tech_code]} {int(max_download)}/{int(max_upload)}"

    if plan_id is not None:
        plan = session.query(service_plan).filter(service_plan.id == plan_id).one_or_none()
        if plan is None or plan.folder_id != folder_id:
            raise ServiceError("Plan not found", 404)
        if plan.tech_code != tech_code:
            # Tech is editable like any other attribute — but a file must
            # never point at a plan of a different technology (the invariant
            # assign_plan_to_file enforces), so moving the plan releases its
            # assignments on files of the old tech. Their legacy columns
            # stand, same as unassigning.
            session.query(file_model).filter(
                file_model.plan_id == plan.id, file_model.techType != tech_code
            ).update({file_model.plan_id: None})
    else:
        plan = service_plan(folder_id=folder_id)
        session.add(plan)

    if is_default:
        session.query(service_plan).filter(
            service_plan.folder_id == folder_id,
            service_plan.tech_code == tech_code,
            service_plan.id != (plan_id or -1),
        ).update({service_plan.is_default: False})

    plan.name = name
    plan.tech_code = tech_code
    plan.max_download = int(max_download)
    plan.max_upload = int(max_upload)
    plan.low_latency = bool(low_latency)
    plan.category = category
    plan.brand = (brand or "").strip() or None
    plan.is_default = bool(is_default)
    session.flush()
    _write_through(plan, session)
    session.commit()
    return plan


def assign_plan_to_file(file_id, plan_id, session):
    """Assign a plan to a coverage file (None clears the assignment, leaving
    the file's legacy columns as they are). Writes the plan through."""
    f = session.query(file_model).filter(file_model.id == file_id).one_or_none()
    if f is None:
        raise ServiceError("File not found", 404)
    if plan_id is None:
        f.plan_id = None
        session.flush()
        # The tech default governs it now — re-stamp from that, not whatever
        # the old assignment left behind.
        if f.techType is not None:
            default = default_plan_for(f.folder_id, f.techType, session)
            if default is not None:
                _write_through(default, session)
        session.commit()
        return f
    plan = session.query(service_plan).filter(service_plan.id == plan_id).one_or_none()
    if plan is None or plan.folder_id != f.folder_id:
        raise ServiceError("Plan not found in this filing", 404)
    if f.techType is not None and plan.tech_code != f.techType:
        raise ServiceError(
            f"{plan.name} is a {TECH_NAMES[plan.tech_code]} plan; this file is not", 400
        )
    f.plan_id = plan.id
    session.flush()
    _write_through(plan, session)
    session.commit()
    return f


def restamp_folder(folderid, session):
    """Re-stamp every coverage file (and its computed kml rows) in a filing
    from the plan governing it, area-edit markers re-applied last. Idempotent.
    Runs inside every recompute, and once as a data migration — the heal for
    filings whose plans were saved before default write-through existed
    (their file columns and kml rows still carried the 0/0 placeholders)."""
    plans = session.query(service_plan).filter(service_plan.folder_id == folderid).all()
    # Defaults first, assignments after — _write_through scopes each plan to
    # the files it governs, so order only matters for readability here.
    for p in sorted(plans, key=lambda x: (not x.is_default, x.id)):
        _write_through(p, session)


def restamp_governing_default(f, session):
    """After a tech change, stamp the file (and its computed kml rows) from
    the plan now governing it — its new tech's default — if one exists. An
    assigned file keeps its assignment's values."""
    if f.plan_id is not None or f.techType is None:
        return
    session.flush()  # the caller just changed f.techType; queries must see it
    default = default_plan_for(f.folder_id, f.techType, session)
    if default is not None:
        _write_through(default, session)


def default_plan_for(folder_id, tech_code, session):
    return (
        session.query(service_plan)
        .filter(
            service_plan.folder_id == folder_id,
            service_plan.tech_code == tech_code,
            service_plan.is_default.is_(True),
        )
        .one_or_none()
    )


def resolve_for_file(f, session):
    """The plan governing a coverage file: its assignment, else its tech's
    default, else None (legacy columns stand alone)."""
    if f.plan_id is not None:
        return session.query(service_plan).filter(service_plan.id == f.plan_id).one_or_none()
    if f.techType is not None:
        return default_plan_for(f.folder_id, f.techType, session)
    return None


def brand_for(plan, organization):
    """Brand resolution: the plan's override, else the provider name (no
    org-level brand field — organization.name doubles as
    brand)."""
    if plan is not None and plan.brand:
        return plan.brand
    return organization.name


def synthesize_legacy_plans(folder_id, session):
    """Give a pre-plans filing a plans view: one plan per distinct
    (tech, down, up, latency, category) across its coverage files, files
    attached, the first plan per tech marked default. Idempotent: does nothing
    if the filing already has plans. Returns the created plans."""
    existing = session.query(service_plan).filter(service_plan.folder_id == folder_id).count()
    if existing:
        return []
    files = (
        session.query(file_model)
        .filter(
            file_model.folder_id == folder_id,
            file_model.techType.isnot(None),
            file_model.plan_id.is_(None),
        )
        .order_by(file_model.id)
        .all()
    )
    created = {}
    seen_tech = set()
    for f in files:
        if f.maxDownloadSpeed is None or f.techType not in TECH_NAMES:
            continue
        key = (f.techType, f.maxDownloadSpeed, f.maxUploadSpeed, f.latency, f.category)
        plan = created.get(key)
        if plan is None:
            plan = service_plan(
                folder_id=folder_id,
                name=f"{TECH_NAMES[f.techType]} {f.maxDownloadSpeed}/{f.maxUploadSpeed}",
                tech_code=f.techType,
                max_download=f.maxDownloadSpeed,
                max_upload=f.maxUploadSpeed,
                low_latency=bool(f.latency),
                category=f.category if f.category in CATEGORY_LABELS else "X",
                is_default=f.techType not in seen_tech,
            )
            seen_tech.add(f.techType)
            session.add(plan)
            session.flush()
            created[key] = plan
        f.plan_id = plan.id
    session.commit()
    return list(created.values())
