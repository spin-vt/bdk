"""Export flow: produce a filing's FCC BDC availability CSV.

Extracted verbatim (behavior-preserving) from routes.export.exportFiling.
"""

from controllers.database_controller import file_ops, folder_ops, kml_ops
from services.exceptions import ServiceError
from utils.namingschemes import DATE_FORMAT, EXPORT_CSV_NAME_TEMPLATE


def create_export_snapshot(folderid, csv_text, brandname, deadline, session):
    """Freeze a filing into an export snapshot: a deep folder copy carrying
    the built CSV, so downloads are byte-stable forever after.

    Called inline by the generate-submission job (the job isn't done until
    the snapshot is downloadable) and by the legacy async copy task.
    """
    csv_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=brandname, deadline=deadline)
    original_folder = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    new_folder = original_folder.copy(
        name=f"Exported Filing for {deadline}",
        type="export",
        deadline=deadline,
        export=True,
        session=session,
    )
    csv_file = file_ops.create_file(
        filename=csv_name,
        content=csv_text.encode("utf-8"),
        folderid=new_folder.id,
        filetype="export",
        session=session,
    )
    session.add(csv_file)
    session.commit()
    return new_folder


def export_filing(user_id, folderid, session, snapshot_inline=False):
    """Build the BDC availability CSV for a filing.

    Returns (csv_bytesio, download_name) on success, or (None, None) if the
    export produced no output. Raises ServiceError(400) for an invalid filing
    id, a filing outside the user's org, or a missing provider id / brand name.

    With snapshot_inline=True the export snapshot is created here, in this
    session, before returning; otherwise it's handed to the detached
    async_folder_copy_for_export task (the legacy /api path's behavior).
    """
    if folderid == -1:
        raise ServiceError("Invalid filing requested", 400)

    if not folder_ops.folder_belongs_to_organization(folderid, user_id, session):
        raise ServiceError("You are accessing a filing not belong to your organization", 400)

    folderVal = folder_ops.get_folder_with_id(folderid=folderid, session=session)
    providerid = folderVal.organization.provider_id
    brandname = folderVal.organization.brand_name
    deadline = folderVal.deadline.strftime(DATE_FORMAT)

    if not providerid or not brandname:
        raise ServiceError("Please provide your provider ID and brand name", 400)

    csv_output = kml_ops.export(
        folderid, providerid, brandname, deadline, session, dispatch_copy=not snapshot_inline
    )
    if not csv_output:
        return None, None

    if snapshot_inline:
        create_export_snapshot(
            folderid, csv_output.getvalue().decode("utf-8"), brandname, deadline, session
        )

    csv_output.seek(0)
    download_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=brandname, deadline=deadline)
    return csv_output, download_name
