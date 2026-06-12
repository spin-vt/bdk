"""Ingestion for the CostQuest Supplemental (pre-v6: "Secondary") address file
into the lean supplemental_data search index.

Same COPY strategy as fabric_ops.write_to_db, but header-driven: the temp
table is created from the CSV's own header (all TEXT) and only the columns the
index keeps are selected out, so vintage-to-vintage schema drift (extra/missing
columns, the primary_secondary -> primary_supplemental rename) doesn't break
the load.
"""

import csv
import io
import re
from threading import Lock

from sqlalchemy import create_engine

from database.models import file
from database.sessions import Session
from utils.settings import DATABASE_URL

db_lock = Lock()

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

# CSV header column -> supplemental_data column. Both historical names of the
# P/S flag map onto the same column; anything not listed is loaded into the
# temp table but never selected out.
_KEPT_COLUMNS = {
    "location_id": "location_id",
    "address": "address",
    "city": "city",
    "state": "state",
    "zip": "zip_code",
    "zip_suffix": "zip_suffix",
    "primary_supplemental": "primary_supplemental",
    "primary_secondary": "primary_supplemental",  # pre-v6 column name
    "address_source": "address_source",
}


def write_to_db(fileid):
    # Own a plain Session (not the request-scoped one) — same reasoning as
    # fabric_ops.write_to_db: this runs in a Celery task, possibly eagerly on
    # the web handler's thread.
    session = Session()
    with db_lock:
        file_record = session.query(file).filter(file.id == fileid).first()
        session.close()

    if not file_record:
        raise ValueError(f"No file found with id {fileid}")

    text = file_record.data.decode()
    header = [h.strip().lower() for h in next(csv.reader(io.StringIO(text)))]
    for col in header:
        if not _IDENT_RE.match(col):
            raise ValueError(f"unexpected column name in supplemental file: {col!r}")
    if "location_id" not in header or "address" not in header:
        raise ValueError("not a supplemental address file (no location_id/address columns)")

    # First header occurrence wins (the real files have no duplicates).
    selected = {}
    for col in header:
        dest = _KEPT_COLUMNS.get(col)
        if dest and dest not in selected:
            selected[dest] = col

    insert_cols = ", ".join([*selected.keys(), "file_id"])
    select_cols = ", ".join(
        [f"{src}::integer" if dest == "location_id" else src for dest, src in selected.items()]
        + [str(int(fileid))]
    )

    engine = create_engine(DATABASE_URL)
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cur:
            col_defs = ", ".join(f"{c} TEXT" for c in header)
            cur.execute(f"CREATE TEMP TABLE temp_supplemental ({col_defs});")
            cur.copy_expert(
                "COPY temp_supplemental FROM STDIN CSV HEADER DELIMITER ','", io.StringIO(text)
            )
            cur.execute(
                f"INSERT INTO supplemental_data ({insert_cols}) "
                f"SELECT {select_cols} FROM temp_supplemental;"
            )
            connection.commit()
    finally:
        connection.close()
