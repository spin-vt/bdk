"""Classify a CostQuest fabric delivery (pure python, no DB).

The delivery is a zip whose own filename is an opaque license key; the inner
CSV filenames carry the signal: `FCC_<role>_<MMDDYYYY>_<release>.csv` where the
role is Active_BSL / Active_NoBSL / Supplemental (historically also bare Active
and Secondary), MMDDYYYY is the data-as-of date, and the release suffix has
changed style over the years (`ver`, `ver2`, `rel_8`, revised `rel_3_2`). For
loose or renamed files a content sniff over the header (and first data row's
bsl_flag) recovers the role, though not the vintage. See
back-end/docs/bdc-fabric-format.md for the full delivery-format history these
rules encode.

Roles:
  active       = Active_BSL    (the fabric proper; drives coverage)
  non_bsl      = Active_NoBSL  (rendered differently, never exported as served)
  supplemental = Supplemental/Secondary (extra addresses; search only)
"""

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime

from services.filing_windows import window_from_deadline

ROLE_ACTIVE = "active"
ROLE_NON_BSL = "non_bsl"
ROLE_SUPPLEMENTAL = "supplemental"

_FILENAME_RE = re.compile(
    r"""fcc[_-]
        (?P<role>active[_-]bsl|active[_-]nobsl|active|supplemental|secondary)[_-]
        (?P<date>\d{8})[_-]
        (?:rel[_-](?P<rel>\d+(?:[_-]\d+)?)|ver(?P<ver>\d+)?)
        \.csv$""",
    re.IGNORECASE | re.VERBOSE,
)

_ROLE_BY_TOKEN = {
    "active_bsl": ROLE_ACTIVE,
    "active": ROLE_ACTIVE,
    "active_nobsl": ROLE_NON_BSL,
    "supplemental": ROLE_SUPPLEMENTAL,
    "secondary": ROLE_SUPPLEMENTAL,
}


@dataclass(frozen=True)
class FabricPart:
    """One classified CSV of a delivery."""

    role: str  # active | non_bsl | supplemental
    data_as_of: date | None  # None when undetectable (renamed/loose file)
    release: str | None  # "8", "3_2", ... None when undetectable
    member: str  # the CSV's filename (zip member name or the upload's name)


@dataclass(frozen=True)
class VintageCheck:
    matches: bool
    expected_version: int
    expected_label: str  # "December 2025"
    got_version: int | None  # None = vintage undetectable


def classify_filename(name):
    """FabricPart from a CSV filename, or None if it doesn't follow any known
    CostQuest naming convention (then try sniff_role on the content)."""
    m = _FILENAME_RE.search(name.rsplit("/", 1)[-1])
    if not m:
        return None
    try:
        data_as_of = datetime.strptime(m.group("date"), "%m%d%Y").date()
    except ValueError:
        return None
    release = m.group("rel") or m.group("ver")
    if release:
        release = release.replace("-", "_")
    return FabricPart(
        role=_ROLE_BY_TOKEN[m.group("role").lower().replace("-", "_")],
        data_as_of=data_as_of,
        release=release,
        member=name,
    )


def sniff_role(head_bytes):
    """Recover the role from CSV content (header set, plus the first data row's
    bsl_flag to split BSL from NoBSL). Returns a role or None."""
    try:
        text = head_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = [h.strip().lower() for h in next(reader)]
    except (StopIteration, csv.Error):
        return None

    if "primary_supplemental" in header or "primary_secondary" in header:
        return ROLE_SUPPLEMENTAL
    if "address_id" in header and "address" in header:
        return ROLE_SUPPLEMENTAL
    if "bsl_flag" in header and "address_primary" in header:
        bsl_idx = header.index("bsl_flag")
        for row in reader:
            if len(row) > bsl_idx:
                # bsl_flag is constant per file (TRUE for Active_BSL, FALSE
                # for Active_NoBSL), so one data row decides.
                return (
                    ROLE_ACTIVE
                    if row[bsl_idx].strip().upper() in ("TRUE", "T", "1")
                    else ROLE_NON_BSL
                )
            break
        return ROLE_ACTIVE  # header-only file: schema says active-family
    return None


# How much of a CSV the sniff reads: enough for the header plus one data row
# even with long quoted fields.
_SNIFF_BYTES = 64 * 1024


def classify_csv(name, data):
    """Classify one CSV: trust the filename when it follows a known convention,
    otherwise sniff the content (role only — vintage is then unknown)."""
    part = classify_filename(name)
    if part is not None:
        return part
    role = sniff_role(data[:_SNIFF_BYTES])
    if role is None:
        return None
    return FabricPart(role=role, data_as_of=None, release=None, member=name)


def inspect_upload(filename, data):
    """Classify a fabric upload (the delivery zip or an individual CSV).

    Returns (parts, unrecognized_names). Anything that is neither a
    classifiable CSV nor a zip member we recognize lands in unrecognized —
    callers decide whether that's an error or just noise (the real zips can
    carry extras like RecordCountByCounty.csv).
    """
    lower = filename.lower()
    if lower.endswith(".zip") or data[:4] == b"PK\x03\x04":
        parts, unrecognized = [], []
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                base = info.filename.rsplit("/", 1)[-1]
                if info.is_dir() or base.startswith(".") or info.filename.startswith("__MACOSX"):
                    continue
                if not base.lower().endswith(".csv"):
                    unrecognized.append(info.filename)
                    continue
                with zf.open(info) as f:
                    head = f.read(_SNIFF_BYTES)
                part = classify_filename(info.filename) or classify_csv(info.filename, head)
                if part is None:
                    unrecognized.append(info.filename)
                else:
                    parts.append(part)
        return parts, unrecognized

    if lower.endswith(".csv"):
        part = classify_csv(filename, data)
        return ([part], []) if part is not None else ([], [filename])

    return [], [filename]


def version_for_data_as_of(data_as_of):
    """Fabric version for a data-as-of date (v1 = June 2022, +1 per window),
    or None for None/off-cycle dates."""
    if data_as_of is None or (data_as_of.month, data_as_of.day) not in ((6, 30), (12, 31)):
        return None
    n = 2 * (data_as_of.year - 2022) + (1 if data_as_of.month == 6 else 2)
    return n if n >= 1 else None


def check_vintage(data_as_of, deadline):
    """Does a delivery's data-as-of date match the fabric version the folder's
    filing window expects? An undetectable vintage counts as a mismatch (the
    user can still override)."""
    window = window_from_deadline(deadline)
    got = version_for_data_as_of(data_as_of)
    return VintageCheck(
        matches=got == window.fabric_version,
        expected_version=window.fabric_version,
        expected_label=window.label,
        got_version=got,
    )
