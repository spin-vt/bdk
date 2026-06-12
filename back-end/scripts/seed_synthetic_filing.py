"""Seed a renderable synthetic filing into the dev DB (for the /app2 prototype).

Creates a folder for the seed user's org, attaches the committed synthetic
dataset (fabric + fiber + two wireless layers), then runs the REAL pipeline
(process_data → coverage + tippecanoe vector tiles). Prints the folder id to
open at /app2/filing/<id>.

Run inside the backend container (has tippecanoe + dev DB):
    docker compose cp dev-data/synthetic backend:/tmp/synthetic
    docker compose exec -e PYTHONPATH=/app backend python scripts/seed_synthetic_filing.py
"""

import datetime
import os
import sys

from controllers.celery_controller.celery_tasks import process_data
from controllers.database_controller import file_ops, folder_ops, user_ops
from database.sessions import Session

SYN = os.environ.get("SYN_DIR", "/tmp/synthetic")
EMAIL = os.environ.get("SEED_EMAIL", "dev@example.com")

# Synthetic tech codes (dev-data/synthetic/README.md): fiber=50, 5GHz=70, 25GHz=71.
COVERAGE = [
    ("fiber.geojson", "wired", 50),
    ("wireless_5ghz.geojson", "wireless", 70),
    ("wireless_25ghz.geojson", "wireless", 71),
]


def _read(name):
    with open(os.path.join(SYN, name), "rb") as fh:
        return fh.read()


def main():
    s = Session()
    user = user_ops.get_user_with_email(EMAIL, s)
    if user is None or isinstance(user, str) or not getattr(user, "organization_id", None):
        print(f"ERROR: no usable user/org for {EMAIL}: {user}")
        sys.exit(1)
    org_id = user.organization_id
    print(f"user={EMAIL} org_id={org_id}")

    folder = folder_ops.create_folder(
        "Synthetic Demo Filing", org_id, datetime.date(2024, 12, 31), "upload", s
    )
    s.commit()
    print(f"created folder_id={folder.id}")

    file_ops.create_file(
        filename="test_fabric.csv",
        content=_read("test_fabric.csv"),
        folderid=folder.id,
        filetype="fabric",
        session=s,
    )
    for fname, ftype, tech in COVERAGE:
        file_ops.create_file(
            filename=fname,
            content=_read(fname),
            folderid=folder.id,
            filetype=ftype,
            techType=tech,
            maxDownloadSpeed=100,
            maxUploadSpeed=20,
            latency=1,
            category="R",
            session=s,
        )
    s.commit()
    print("files created; running process_data (coverage + tippecanoe tiling)...")

    process_data.apply(args=[folder.id, 2]).get()
    print(f"DONE — open /app2/filing/{folder.id}")


if __name__ == "__main__":
    main()
