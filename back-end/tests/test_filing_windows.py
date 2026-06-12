"""BDC filing-window math (services/filing_windows.py) — pure unit tests.

Pins the real-world mapping from back-end/docs/bdc-fabric-format.md: window
<-> fabric version <-> due date with weekend rollover.
"""

from datetime import date

from services.filing_windows import (
    next_window,
    open_window,
    window_for,
    window_from_deadline,
)


def test_fabric_version_mapping():
    assert window_for(2022, 6).fabric_version == 1
    assert window_for(2022, 12).fabric_version == 2
    assert window_for(2024, 12).fabric_version == 6
    assert window_for(2025, 12).fabric_version == 8
    # The design prototype's example values (June 2026 -> v6 / December 2026
    # -> v7) were WRONG; the real mapping counts up from v1 = June 2022.
    assert window_for(2026, 6).fabric_version == 9
    assert window_for(2026, 12).fabric_version == 10


def test_due_dates_roll_weekends():
    # March 1, 2026 is a Sunday -> March 2 (the documented real case).
    assert window_for(2025, 12).due == date(2026, 3, 2)
    # September 1, 2024 is a Sunday -> September 2.
    assert window_for(2024, 6).due == date(2024, 9, 2)
    # September 1, 2026 is a Tuesday -> no roll.
    assert window_for(2026, 6).due == date(2026, 9, 1)


def test_labels_and_data_as_of():
    w = window_for(2026, 6)
    assert w.label == "June 2026"
    assert w.data_as_of == date(2026, 6, 30)


def test_window_from_deadline_classifies_user_entered_dates():
    # Canonical due dates map to their window.
    assert window_from_deadline(date(2024, 9, 1)).label == "June 2024"
    assert window_from_deadline(date(2026, 3, 2)).label == "December 2025"
    # Prod-style "data as of" deadlines map to the window the user meant.
    assert window_from_deadline(date(2025, 12, 31)).label == "December 2025"
    assert window_from_deadline(date(2026, 6, 30)).label == "June 2026"


def test_open_and_next_window():
    # 2026-06-10: December 2025 closed March 2; June 2026 data date not reached.
    assert open_window(date(2026, 6, 10)) is None
    assert next_window(date(2026, 6, 10)).label == "June 2026"
    # 2026-07-15: June 2026 window is open (data passed, due Sept 1 ahead).
    assert open_window(date(2026, 7, 15)).label == "June 2026"
    # On the due date it still counts as open.
    assert open_window(date(2026, 9, 1)).label == "June 2026"
    # The day after, it's closed and December 2026 is next.
    assert open_window(date(2026, 9, 2)) is None
    assert next_window(date(2026, 9, 2)).label == "December 2026"
