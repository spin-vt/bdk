"""Filing flows: create / copy / delete and related orchestration.

Extracted verbatim (behavior-preserving) from the routes.filings handlers.
"""

from controllers.celery_controller.celery_tasks import async_folder_delete
from controllers.database_controller import celerytaskinfo_ops, folder_ops, user_ops
from services.exceptions import ServiceError


def delete_filing(user_id, folderid, session):
    """Authorize the folder against the user's org, dispatch the async delete,
    and record a Delete task-info row. Returns the celery task id.

    Raises ServiceError(400) if the folder doesn't belong to the user's org.
    """
    if not folder_ops.folder_belongs_to_organization(
        folder_id=folderid, user_id=user_id, session=session
    ):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)

    userVal = user_ops.get_user_with_id(userid=user_id, session=session)
    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    deadline = folderVal.deadline
    result = async_folder_delete.apply_async(args=[folderid])
    celerytaskinfo_ops.create_celery_taskinfo(
        task_id=result.task_id,
        status="PENDING",
        operation_type="Delete",
        operation_detail="Delete a filing",
        user_email=userVal.email,
        organization_id=userVal.organization_id,
        folder_deadline=deadline,
        session=session,
    )
    return result.task_id


def _owned_upload_folder(user_id, folderid, session):
    if not folder_ops.folder_belongs_to_organization(
        folder_id=folderid, user_id=user_id, session=session
    ):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)
    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    if folderVal.type != "upload":
        raise ServiceError("Only filings can be marked filed or reopened", 400)
    return folderVal


def mark_filed(user_id, folderid, session):
    """Explicitly mark a filing as filed (the user uploaded the generated CSV
    in the FCC portal). Deadlines passing never auto-files; this is always a
    user action, and reopen() undoes it."""
    from datetime import datetime

    folderVal = _owned_upload_folder(user_id, folderid, session)
    folderVal.status = "filed"
    folderVal.filed_at = datetime.utcnow()
    session.commit()
    return folderVal


def reopen(user_id, folderid, session):
    """Reopen a filed filing for edits (changes then need a new submission)."""
    folderVal = _owned_upload_folder(user_id, folderid, session)
    folderVal.status = "open"
    folderVal.filed_at = None
    session.commit()
    return folderVal


def assert_window_available(organization_id, deadline_date, session):
    """One filing per org per BDC window: refuse creating a second upload
    filing whose deadline classifies into the same window as an existing one."""
    from database.models import folder as folder_model
    from services import filing_windows

    target = filing_windows.window_from_deadline(deadline_date)
    existing = (
        session.query(folder_model)
        .filter(
            folder_model.organization_id == organization_id,
            folder_model.type == "upload",
        )
        .all()
    )
    for f in existing:
        if f.deadline and filing_windows.window_from_deadline(f.deadline).label == target.label:
            raise ServiceError(
                f"Your organization already has a filing for the {target.label} window",
                400,
            )


def switcher_data(user_id, session, today=None):
    """Everything the header filing switcher shows: the org's filings labeled
    by window (newest first, each with status), plus the next window to
    announce if no filing exists for it yet."""
    from datetime import date as _date

    from database.models import folder as folder_model
    from services import filing_windows

    today = today or _date.today()
    userVal = user_ops.get_user_with_id(userid=user_id, session=session)
    filings = []
    if userVal and userVal.organization_id:
        rows = (
            session.query(folder_model)
            .filter(
                folder_model.organization_id == userVal.organization_id,
                folder_model.type == "upload",
            )
            .order_by(folder_model.deadline.desc())
            .all()
        )
        for f in rows:
            w = filing_windows.window_from_deadline(f.deadline) if f.deadline else None
            filings.append(
                {
                    "id": f.id,
                    "label": w.label if w else f.name,
                    "due": w.due.isoformat() if w else None,
                    "status": f.status or "open",
                }
            )
    upcoming = filing_windows.next_window(today)
    have_upcoming = any(f["label"] == upcoming.label for f in filings)
    return {
        "filings": filings,
        "next_window": None
        if have_upcoming
        else {"label": upcoming.label, "due": upcoming.due.isoformat()},
    }


def submission_debts(user_id, folderid, session):
    """The debt selector: everything standing between this filing and a
    submission, in plain words with a place to fix it. Empty list = ready.
    Feeds the header badge ("N tasks to finish" / "Ready to submit") and the
    generate sheet — the app's only hard gate."""
    from database.models import file as file_model
    from services import plan_service

    folderVal = _owned_upload_folder(user_id, folderid, session)

    debts = []

    has_fabric = (
        session.query(file_model)
        .filter(file_model.folder_id == folderVal.id, file_model.type == "fabric")
        .first()
        is not None
    )
    if not has_fabric:
        debts.append(
            {
                "id": "fabric",
                "label": "No fabric loaded",
                "sub": "served locations can't be computed without it",
                "fix": "/files?tab=fabric",
            }
        )

    coverage_files = (
        session.query(file_model)
        .filter(file_model.folder_id == folderVal.id, file_model.type.in_(("wired", "wireless")))
        .all()
    )
    if not coverage_files:
        # An empty CSV is technically submittable, but "Ready to submit" with
        # nothing on the map is just confusing.
        debts.append(
            {
                "id": "coverage",
                "label": "No network coverage yet",
                "sub": "add at least one coverage file so there's something to submit",
                "fix": "/files?tab=coverage",
            }
        )
    for tech in sorted({f.techType for f in coverage_files if f.techType is not None}):
        if plan_service.default_plan_for(folderVal.id, tech, session) is None:
            name = plan_service.TECH_NAMES.get(tech, str(tech))
            debts.append(
                {
                    "id": f"plan:{tech}",
                    "label": f"{name} ({tech}) has no default plan",
                    "sub": "every technology needs one plan to submit",
                    "fix": "/files?tab=plans",
                }
            )

    org = folderVal.organization
    if not org or not org.provider_id:
        debts.append(
            {
                "id": "provider_id",
                "label": "BDC Provider ID missing",
                "sub": "the FCC rejects a filing without it",
                "fix": "/org",
            }
        )

    return debts


def _verified_org_user(user_id, session):
    userVal = user_ops.get_user_with_id(user_id, session=session)
    if not userVal or not userVal.organization_id:
        raise ServiceError("Create or join an organization first", 400)
    if not userVal.verified:
        raise ServiceError("Please Verify your email to start working on a filing", 400)
    return userVal


def _materialize_filing(userVal, window, source_folder, session):
    """Create the filing for `window`, copying from `source_folder` when given
    or starting empty. The copy is SYNCHRONOUS — when this returns, the new
    filing exists and the caller can select it and land the user on it (no
    async race where the page refreshes before the worker has created
    anything). Everything carries forward (files, plans with remapped
    assignments, edits with their markers); the old fabric is deliberately
    dropped — each window needs its own delivery, and its intake triggers the
    recompute."""
    if source_folder is not None:
        new_folder = source_folder.copy(
            name=f"Filing for Deadline {window.due.isoformat()}",
            type="upload",
            deadline=window.due,
            export=False,
            session=session,
        )
        session.commit()
        # The pill narrates the background half (tile build for the carried
        # geometry; the coverage compute itself waits for the new fabric).
        from controllers.celery_controller.celery_tasks import process_data

        result = process_data.apply_async(args=[new_folder.id, 3])
        celerytaskinfo_ops.create_celery_taskinfo(
            task_id=result.task_id,
            status="PENDING",
            operation_type="Upload",
            operation_detail=(
                "Create a new Filing by importing from filing with deadline "
                f"{source_folder.deadline.strftime('%Y-%m')}"
            ),
            user_email=userVal.email,
            organization_id=userVal.organization_id,
            folder_deadline=window.due,
            session=session,
        )
    else:
        new_folder = folder_ops.create_folder(
            f"Filing for Deadline {window.due.isoformat()}",
            userVal.organization_id,
            window.due,
            "upload",
            session,
        )
        session.commit()
    return new_folder


def start_next_filing(user_id, session, today=None):
    """Create the next window's filing — ALWAYS an explicit user action (the
    switcher's "+ Start the <window> filing" button; never automatic).

    Carries the latest filing forward when one exists; a first-time org starts
    an empty filing. One filing per org per window. Returns the new folder."""
    from datetime import date as _date

    from services import filing_windows

    userVal = _verified_org_user(user_id, session)
    upcoming = filing_windows.next_window(today or _date.today())
    assert_window_available(userVal.organization_id, upcoming.due, session)

    current = folder_ops.get_upload_folder(orgid=userVal.organization_id, session=session)
    if current is None or isinstance(current, str):
        current = None
    return _materialize_filing(userVal, upcoming, current, session)


def pick_import_source(organization_id, due, session):
    """The default "copy from" for a new filing: the latest existing filing
    BEFORE its window (never import from the future by default); when
    everything existing is later — an org backfilling its oldest window —
    the earliest is the closest there is. None with no filings."""
    from database.models import folder as folder_model

    rows = (
        session.query(folder_model)
        .filter(
            folder_model.organization_id == organization_id,
            folder_model.type == "upload",
            folder_model.deadline.isnot(None),
        )
        .order_by(folder_model.deadline.asc())
        .all()
    )
    if not rows:
        return None
    earlier = [f for f in rows if f.deadline < due]
    return earlier[-1] if earlier else rows[0]


def start_filing_for_window(user_id, year, month, session, source="auto", today=None):
    """Create a filing for ANY opened window — the switcher's "Create new
    filing…" modal (e.g. an org bringing its old filings in). `source` is
    "scratch", "auto" (pick_import_source's nearest-earlier default), or a
    folder id to copy from. Only windows whose due date isn't past the next
    window's can be created — nothing stops working on an old filing, but a
    far-future one doesn't exist yet. One filing per org per window."""
    from datetime import date as _date

    from services import filing_windows

    userVal = _verified_org_user(user_id, session)
    try:
        year, month = int(year), int(month)
    except (TypeError, ValueError):
        raise ServiceError("Pick June or December and a year", 400) from None
    if year < 2022:
        raise ServiceError("BDC filings began with the June 2022 window", 400)
    try:
        w = filing_windows.window_for(year, month)
    except ValueError:
        raise ServiceError("Pick June or December and a year", 400) from None
    today = today or _date.today()
    if w.due > filing_windows.next_window(today).due:
        raise ServiceError(f"The {w.label} window hasn't opened yet", 400)
    assert_window_available(userVal.organization_id, w.due, session)

    if source == "scratch":
        source_folder = None
    elif source in (None, "", "auto"):
        source_folder = pick_import_source(userVal.organization_id, w.due, session)
    else:
        try:
            source_id = int(source)
        except (TypeError, ValueError):
            raise ServiceError("Pick a filing to copy from", 400) from None
        if not folder_ops.folder_belongs_to_organization(source_id, user_id, session):
            raise ServiceError("You are accessing a filing not belong to your organization", 400)
        source_folder = folder_ops.get_folder_with_id(folderid=source_id, session=session)
        if (
            source_folder is None
            or isinstance(source_folder, str)
            or source_folder.type != "upload"
        ):
            raise ServiceError("Pick a filing to copy from", 400)
    return _materialize_filing(userVal, w, source_folder, session)
