"""CostQuest fabric delivery classification (services/fabric_intake.py) — pure
unit tests, no DB.

Pins the interop facts from back-end/docs/bdc-fabric-format.md: filename
patterns across the whole naming history (v1 `ver` .. v8 `rel_8`, revised
`rel_3_2`), the
content-sniff fallback for renamed/loose files, zip inspection, and the
vintage <-> filing-window check. Fixtures are synthetic but shaped exactly like
the real delivery (mixed quoting, CRLF).
"""

import io
import zipfile
from datetime import date

from services.fabric_intake import (
    check_vintage,
    classify_csv,
    classify_filename,
    inspect_upload,
    sniff_role,
    version_for_data_as_of,
)

# CostQuest-shaped synthetic CSVs (headers byte-identical to the real v6/v8
# deliveries; tier 2/3/4: fcc_rel present).
from tests.conftest_helpers import (
    make_active_fabric_csv as active_csv_bytes,
)
from tests.conftest_helpers import (
    make_supplemental_csv as supplemental_csv_bytes,
)


def make_zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()


# --- filename classification across the naming history ------------------------


def test_current_era_rel_suffix():
    p = classify_filename("FCC_Active_BSL_12312025_rel_8.csv")
    assert (p.role, p.data_as_of, p.release) == ("active", date(2025, 12, 31), "8")

    p = classify_filename("FCC_Active_NoBSL_12312025_rel_8.csv")
    assert (p.role, p.data_as_of, p.release) == ("non_bsl", date(2025, 12, 31), "8")

    p = classify_filename("FCC_Supplemental_12312024_rel_6.csv")
    assert (p.role, p.data_as_of, p.release) == ("supplemental", date(2024, 12, 31), "6")


def test_revised_release_mid_window():
    # The real July-2023 revised fabric: rel_3_2.
    p = classify_filename("FCC_Active_BSL_06302023_rel_3_2.csv")
    assert (p.role, p.data_as_of, p.release) == ("active", date(2023, 6, 30), "3_2")


def test_v1_era_two_file_naming():
    # v1 (Jun 2022): bare Active + Secondary, suffix "ver".
    p = classify_filename("FCC_Active_06302022_ver.csv")
    assert (p.role, p.data_as_of, p.release) == ("active", date(2022, 6, 30), None)

    p = classify_filename("FCC_Secondary_06302022_ver.csv")
    assert (p.role, p.data_as_of) == ("supplemental", date(2022, 6, 30))


def test_v2_era_verx_suffix():
    p = classify_filename("FCC_Active_BSL_12312022_ver2.csv")
    assert (p.role, p.data_as_of, p.release) == ("active", date(2022, 12, 31), "2")

    p = classify_filename("FCC_Active_NoBSL_12312022_ver2.csv")
    assert p.role == "non_bsl"


def test_classification_is_case_insensitive_and_path_tolerant():
    p = classify_filename("delivery/fcc_active_bsl_12312025_REL_8.CSV")
    assert (p.role, p.release) == ("active", "8")


def test_unrecognized_filenames_return_none():
    assert classify_filename("RecordCountByCounty.csv") is None
    assert classify_filename("my_fabric.csv") is None
    assert classify_filename("FCC_Active_BSL_12312025_rel_8.txt") is None
    # Garbage date does not classify (falls through to the content sniff).
    assert classify_filename("FCC_Active_BSL_99889999_rel_8.csv") is None


# --- content sniff fallback ----------------------------------------------------


def test_sniff_active_bsl_vs_nobsl():
    bsl = active_csv_bytes([(1001, "1 MAIN ST", "TRUE", 37.27, -79.94, "51161", "VA")])
    nobsl = active_csv_bytes([(1002, "2 MAIN ST", "FALSE", 37.27, -79.94, "51161", "VA")])
    assert sniff_role(bsl) == "active"
    assert sniff_role(nobsl) == "non_bsl"


def test_sniff_supplemental_both_column_names():
    assert sniff_role(supplemental_csv_bytes([(1001, "S", "1 MAIN STREET")])) == "supplemental"
    # Pre-v6 column name: primary_secondary.
    legacy = supplemental_csv_bytes([(1001, "S", "1 MAIN STREET")]).replace(
        b"primary_supplemental", b"primary_secondary"
    )
    assert sniff_role(legacy) == "supplemental"


def test_sniff_rejects_unrelated_csv():
    assert sniff_role(b'"a","b","c"\r\n1,2,3\r\n') is None


def test_classify_csv_prefers_filename_then_sniffs():
    data = active_csv_bytes([(1001, "1 MAIN ST", "TRUE", 37.27, -79.94, "51161", "VA")])
    p = classify_csv("FCC_Active_BSL_12312025_rel_8.csv", data)
    assert (p.role, p.data_as_of) == ("active", date(2025, 12, 31))
    # Renamed: role comes from the content, vintage unknown.
    p = classify_csv("our-fabric-renamed.csv", data)
    assert (p.role, p.data_as_of, p.release) == ("active", None, None)


# --- zip inspection -------------------------------------------------------------


def test_inspect_zip_classifies_members_and_reports_extras():
    z = make_zip(
        [
            (
                "FCC_Active_BSL_12312025_rel_8.csv",
                active_csv_bytes([(1001, "1 MAIN ST", "TRUE", 37.27, -79.94, "51161", "VA")]),
            ),
            (
                "FCC_Active_NoBSL_12312025_rel_8.csv",
                active_csv_bytes([(2001, "1 SCHOOL RD", "FALSE", 37.28, -79.95, "51161", "VA")]),
            ),
            (
                "FCC_Supplemental_12312025_rel_8.csv",
                supplemental_csv_bytes([(1001, "S", "ONE MAIN STREET")]),
            ),
            ("RecordCountByCounty.csv", b'"StateFIPS","CountyFIPS","BSL_LocationCount"\r\n'),
        ]
    )
    # The zip's own name is an opaque license key — carries no signal.
    parts, unrecognized = inspect_upload("H5PKFG71-OPAQUE.zip", z)
    assert sorted(p.role for p in parts) == ["active", "non_bsl", "supplemental"]
    assert all(p.data_as_of == date(2025, 12, 31) for p in parts)
    assert unrecognized == ["RecordCountByCounty.csv"]


def test_inspect_single_csv():
    data = active_csv_bytes([(1001, "1 MAIN ST", "TRUE", 37.27, -79.94, "51161", "VA")])
    parts, unrecognized = inspect_upload("FCC_Active_BSL_12312025_rel_8.csv", data)
    assert len(parts) == 1 and parts[0].role == "active"
    assert unrecognized == []


def test_inspect_rejects_other_extensions():
    parts, unrecognized = inspect_upload("fabric.xlsx", b"junk")
    assert parts == [] and unrecognized == ["fabric.xlsx"]


# --- vintage <-> window --------------------------------------------------------


def test_version_for_data_as_of():
    assert version_for_data_as_of(date(2025, 12, 31)) == 8
    assert version_for_data_as_of(date(2024, 12, 31)) == 6
    assert version_for_data_as_of(date(2022, 6, 30)) == 1
    # June 2026 -> v9, December 2026 -> v10 (the design prototype's v6/v7
    # example values were wrong).
    assert version_for_data_as_of(date(2026, 6, 30)) == 9
    assert version_for_data_as_of(date(2026, 12, 31)) == 10
    # Off-cycle dates carry no version.
    assert version_for_data_as_of(date(2025, 3, 1)) is None
    assert version_for_data_as_of(None) is None


def test_check_vintage_match_and_mismatch():
    # A folder deadline near the December-2025 window expects v8 fabric.
    ok = check_vintage(date(2025, 12, 31), deadline=date(2026, 3, 2))
    assert ok.matches and ok.expected_version == 8 and ok.got_version == 8

    stale = check_vintage(date(2024, 12, 31), deadline=date(2026, 3, 2))
    assert not stale.matches
    assert (stale.expected_version, stale.got_version) == (8, 6)
    assert stale.expected_label == "December 2025"


def test_check_vintage_unknown_data_as_of_is_a_mismatch():
    # A renamed file with no detectable vintage must still trip the warning.
    unknown = check_vintage(None, deadline=date(2026, 3, 2))
    assert not unknown.matches
    assert unknown.got_version is None and unknown.expected_version == 8
