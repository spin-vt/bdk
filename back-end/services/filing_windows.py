"""BDC filing-window math (pure python, no DB).

Everything in the BDC process is referred to by its "data as of" date (June 30
/ December 31) except the Fabric, which goes by version number (see
back-end/docs/bdc-fabric-format.md):

  - data as of June 30 of year Y  -> due the following September 1
  - data as of December 31 of Y   -> due the following March 1
  - due dates falling on a weekend roll to the next business day
    (e.g. March 1, 2026 was a Sunday -> due March 2, 2026)
  - fabric versions count up one per window from v1 = June 2022
    (June Y -> 2*(Y-2022)+1, December Y -> 2*(Y-2022)+2; June 2026 -> v9)

A `folder`'s `deadline` is user-entered today and not necessarily a canonical
due date (prod has deadlines like 2025-12-31), so classification maps a
deadline to the window whose due date is nearest.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Window:
    label: str  # "June 2026"
    data_as_of: date  # 2026-06-30
    fabric_version: int  # 9
    due: date  # 2026-09-01, weekend-rolled

    @property
    def year(self):
        return self.data_as_of.year

    @property
    def month(self):
        return self.data_as_of.month


def _next_business_day(d):
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d += timedelta(days=1)
    return d


def window_for(year, month):
    """The filing window for a data-as-of (year, June|December)."""
    if month == 6:
        return Window(
            label=f"June {year}",
            data_as_of=date(year, 6, 30),
            fabric_version=2 * (year - 2022) + 1,
            due=_next_business_day(date(year, 9, 1)),
        )
    if month == 12:
        return Window(
            label=f"December {year}",
            data_as_of=date(year, 12, 31),
            fabric_version=2 * (year - 2022) + 2,
            due=_next_business_day(date(year + 1, 3, 1)),
        )
    raise ValueError(f"BDC windows are June or December, not month {month}")


def window_from_deadline(deadline):
    """Classify a folder's (user-entered) deadline date into its filing window:
    the window whose due date is nearest."""
    candidates = []
    for y in (deadline.year - 1, deadline.year, deadline.year + 1):
        candidates.append(window_for(y, 6))
        candidates.append(window_for(y, 12))
    return min(candidates, key=lambda w: abs((w.due - deadline).days))


def open_window(today):
    """The window currently accepting filings (its data date has passed, its
    due date hasn't), or None between windows."""
    for w in _recent_windows(today):
        if w.data_as_of < today <= w.due:
            return w
    return None


def next_window(today):
    """The next window whose due date is still ahead (the one to announce)."""
    upcoming = [w for w in _recent_windows(today) if w.due >= today]
    return min(upcoming, key=lambda w: w.due)


def _recent_windows(today):
    out = []
    for y in (today.year - 1, today.year, today.year + 1):
        out.append(window_for(y, 6))
        out.append(window_for(y, 12))
    return out
