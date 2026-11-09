"""The season's windows: the days the trend model is fitted on, and the days the season panels
show. One pair for every taxon, from the counting effort alone.

A season day belongs to a window when it was counted (`state == "counted"`) in at least a share of
the years from `export.SYSTEMATIC_FROM` (daily systematic counting) to the last complete year,
that share smoothed over `ENVELOPE_SMOOTH` days so a one-off gap does not cut the run:
`MODEL_MIN_YEARS` for the model, which fills the rest, `VIEW_MIN_YEARS` for the panels, which
only show what was counted. Both are clipped to `profile.PROFILE_DOY`, the days the time-of-day
profile and the season frame cover. No taxon's passage enters the rule, so every taxon's totals,
shares and passage dates are over the same days (`DECISIONS.md` -> `window@3`).

On the 2025 release this gives 14 Jul - 1 Dec for the model and 11 Jul - 2 Dec for the panels;
the default window (`export.WINDOW`, 18 Jul - 18 Nov) stays the standard period of the yearly
index.

Whether a taxon still passes where counting starts or stops is not a property of the window: it
is judged from the counts alone (`edges`).

Windows are pairs of season days (`trend.season_day`: the day of year of a non-leap year, so one
calendar date is one day every year), inclusive. `settings` can override both.
"""

import numpy as np
import pandas as pd

from defile_explore.export import SYSTEMATIC_FROM, WINDOW
from defile_explore.profile import PROFILE_DOY
from defile_explore.trend import season_day

METHOD = "window@3"
MODEL_MIN_YEARS = 1 / 3  # share of years a date must be counted in to be modelled
VIEW_MIN_YEARS = 0.1  # ... to be shown
ENVELOPE_SMOOTH = 7  # days of the rolling mean of that share (one-off gaps do not cut it)
NON_LEAP = 2001  # a non-leap year, to turn (month, day) into a season day and back


def season_day_of(month: int, day: int) -> int:
    return pd.Timestamp(NON_LEAP, month, day).dayofyear


def default_window() -> tuple[int, int]:
    return season_day_of(*WINDOW[0]), season_day_of(*WINDOW[1])


def as_dates(window: tuple[int, int]) -> list[str]:
    """A window as `MM-DD` strings."""
    base = pd.Timestamp(NON_LEAP, 1, 1)
    return [(base + pd.Timedelta(days=d - 1)).strftime("%m-%d") for d in window]


def from_dates(dates: list[str]) -> tuple[int, int]:
    """A window from `MM-DD` strings (as in `overrides.yaml`)."""
    return tuple(season_day_of(*map(int, d.split("-"))) for d in dates)


def counted_share(effort: pd.DataFrame, last_year: int) -> pd.Series:
    """Share of the years `SYSTEMATIC_FROM`..`last_year` in which each season day of `PROFILE_DOY`
    was counted, smoothed over `ENVELOPE_SMOOTH` days."""
    e = effort[effort["state"] == "counted"]
    years = e["date"].dt.year
    e = e[(years >= SYSTEMATIC_FROM) & (years <= last_year)]
    doy = pd.Series(season_day(pd.DatetimeIndex(e["date"])), index=e.index)
    share = e["date"].dt.year.groupby(doy).nunique() / (last_year - SYSTEMATIC_FROM + 1)
    share = share.reindex(range(PROFILE_DOY[0], PROFILE_DOY[1] + 1), fill_value=0.0)
    return share.rolling(ENVELOPE_SMOOTH, center=True, min_periods=1).mean()


def span(share: pd.Series, min_years: float) -> tuple[int, int]:
    """The run of days around the best-counted day with `share >= min_years`."""
    ok = (share >= min_years).to_numpy()
    days = share.index.to_numpy()
    peak = int(np.argmax(share.to_numpy()))
    lo = hi = peak
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < len(ok) - 1 and ok[hi + 1]:
        hi += 1
    return int(days[lo]), int(days[hi])


def windows(effort: pd.DataFrame, last_year: int) -> dict:
    """The `model` and `view` windows, the same for every taxon (see the module docstring)."""
    share = counted_share(effort, last_year)
    return {
        "method": METHOD,
        "model": span(share, MODEL_MIN_YEARS),
        "view": span(share, VIEW_MIN_YEARS),
    }
