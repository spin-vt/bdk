"""One-off data policy for upgrading a legacy (pre-filing-model) database,
run once after `alembic upgrade head` (see deploy/restore-and-migrate.sh).
Idempotent — safe to re-run; prints one line per decision.

1. Upload filings whose filing window is already past are marked filed:
   under the old model "filed" didn't exist, and anything from a closed
   window was necessarily submitted (or abandoned) long ago. Filings in the
   open or a future window stay open.
2. Service plans are synthesized for every upload filing from its files'
   legacy speed columns (plan_service.synthesize_legacy_plans): one plan per
   distinct tech/down/up/latency/category combination, the first per
   technology marked the tech default, files attached. Export snapshots stay
   plan-less — they are frozen history and resolution falls back to file
   columns.
"""

from datetime import date, datetime

from database.models import folder
from database.sessions import Session
from services import filing_windows, plan_service


def main():
    session = Session()
    now = date.today()
    uploads = session.query(folder).filter(folder.type == "upload").order_by(folder.id).all()
    for f in uploads:
        w = filing_windows.window_from_deadline(f.deadline)
        if f.status == "filed":
            print(f"folder {f.id} ({w.label}): already filed")
        elif w.due < now:
            f.status = "filed"
            if f.filed_at is None:
                f.filed_at = datetime.combine(w.due, datetime.min.time())
            print(f"folder {f.id} ({w.label}, was due {w.due}): marked filed")
        else:
            print(f"folder {f.id} ({w.label}, due {w.due}): left open")

        plans = plan_service.synthesize_legacy_plans(f.id, session)
        if plans:
            for p in plans:
                print(
                    f"  plan: {p.name} (tech {p.tech_code}, "
                    f"{p.max_download}/{p.max_upload}, "
                    f"{'default' if p.is_default else 'extra'})"
                )
        else:
            print("  plans: already present")
    session.commit()
    session.close()


if __name__ == "__main__":
    main()
