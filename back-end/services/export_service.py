"""Export flow: produce a filing's FCC BDC availability CSV.

Extracted verbatim (behavior-preserving) from routes.export.exportFiling.
"""

from controllers.database_controller import folder_ops, kml_ops
from services.exceptions import ServiceError
from utils.namingschemes import DATE_FORMAT, EXPORT_CSV_NAME_TEMPLATE


def export_filing(user_id, folderid, session):
    """Build the BDC availability CSV for a filing.

    Returns (csv_bytesio, download_name) on success, or (None, None) if the
    export produced no output. Raises ServiceError(400) for an invalid filing
    id, a filing outside the user's org, or a missing provider id / brand name.
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

    csv_output = kml_ops.export(folderid, providerid, brandname, deadline, session)
    if not csv_output:
        return None, None

    csv_output.seek(0)
    download_name = EXPORT_CSV_NAME_TEMPLATE.format(brand_name=brandname, deadline=deadline)
    return csv_output, download_name
