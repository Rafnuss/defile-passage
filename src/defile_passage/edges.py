"""Whether a taxon is still passing when counting starts or stops: the `edges` of the window block,
from the counts alone, whatever window the model uses.

Each year has its own counting season: the days of regular counting, from the first to the last
counted day in a run of `REGULAR_SPAN` days with at least `REGULAR_DAYS` of them counted
(`regular_seasons`). Late in the season the count goes on sporadically, on days picked for their
weather, when birds are expected: those days would make the late edge look busier than it is, and
are left out, as are the days before regular counting starts.

At each end (`early`, `late`), the edge is the first or last `EDGE_DAYS` of each year's regular
counting. Its `index` is the birds per full counted day there against the whole season's, each a
ratio estimator over the years (Σ birds / Σ c, days with `c >= COVERAGE_MIN`, as the yearly index):
1 means birds pass at the edge as fast as on an average day of the season. A bootstrap over years
(`DRAWS`) gives `q10`. The edge's `level` is `consistent` when `q10 >= EDGE_INDEX` (birds pass at
the edge in most years), `some_years` when only the index is (a few years with passage at the edge:
Common Crane in November), else null. `consistent` is the taxon's `beyond_counting`: its passage
likely continues beyond regular counting, and its totals and dates miss those birds.
"""

import numpy as np
import pandas as pd

from defile_passage.profile import COVERAGE_MIN

METHOD = "edges@1"
REGULAR_SPAN = 7  # days around a counted day...
REGULAR_DAYS = 5  # ... at least this many counted: regular counting
EDGE_DAYS = 7  # days at each end of a year's regular counting
EDGE_INDEX = 1.0  # birds per full day at the edge against the season's average day
EDGE_QUANTILE = 0.1  # ... reached by this bootstrap quantile: `consistent`
DRAWS = 2000  # bootstrap draws over years
SEED = 20261109
LEVELS = ("consistent", "some_years")


def regular_seasons(effort: pd.DataFrame) -> pd.DataFrame:
    """Per year, the first and last day of regular counting (`first`, `last`)."""
    counted = effort.loc[effort["state"] == "counted", "date"]
    rows = []
    for year, dates in counted.groupby(counted.dt.year):
        days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
        s = pd.Series(days.isin(dates).astype(int), index=days)
        # a counted day in some run of REGULAR_SPAN days with REGULAR_DAYS counted
        full = s.rolling(REGULAR_SPAN, min_periods=1).sum() >= REGULAR_DAYS  # run ending here
        within = full[::-1].rolling(REGULAR_SPAN, min_periods=1).max()[::-1].astype(bool)
        regular = s.index[(s == 1) & within]
        if len(regular):
            rows.append({"year": year, "first": regular.min(), "last": regular.max()})
    return pd.DataFrame(rows, columns=["year", "first", "last"]).set_index("year")


def edge_sums(
    days: pd.DataFrame, effort: pd.DataFrame, c: pd.Series, first_year: int, last_year: int
) -> pd.DataFrame:
    """Per year of `first_year`..`last_year`, birds and coverage summed over the regular season's
    days with `c >= COVERAGE_MIN` (`b`, `c`), its first `EDGE_DAYS` (`b_early`, `c_early`) and its
    last (`b_late`, `c_late`).

    Counted days without a record of the taxon count as zero.
    """
    seasons = regular_seasons(effort)
    e = effort.assign(c=c)
    e = e[(e["state"] == "counted") & (e["c"] >= COVERAGE_MIN)]
    year = e["date"].dt.year
    e = e[year.between(first_year, last_year) & year.isin(seasons.index)]
    year = e["date"].dt.year
    first = year.map(seasons["first"])
    last = year.map(seasons["last"])
    e = e[(e["date"] >= first) & (e["date"] <= last)]
    first, last, year = first[e.index], last[e.index], year[e.index]
    b = e["date"].map(days.set_index("date")["count"]).fillna(0.0)
    early = (e["date"] - first).dt.days < EDGE_DAYS
    late = (last - e["date"]).dt.days < EDGE_DAYS
    frame = pd.DataFrame(
        {
            "b": b,
            "c": e["c"],
            "b_early": b * early,
            "c_early": e["c"] * early,
            "b_late": b * late,
            "c_late": e["c"] * late,
        }
    )
    return frame.groupby(year).sum()


def _index(sums: np.ndarray, end: str, columns) -> np.ndarray:
    """Edge index from summed columns (last axis), NaN where undefined."""
    col = {k: i for i, k in enumerate(columns)}
    with np.errstate(divide="ignore", invalid="ignore"):
        edge = sums[..., col[f"b_{end}"]] / sums[..., col[f"c_{end}"]]
        season = sums[..., col["b"]] / sums[..., col["c"]]
        return edge / season


def edges_block(
    days: pd.DataFrame, effort: pd.DataFrame, c: pd.Series, first_year: int, last_year: int
) -> dict:
    """`{method, early, late, beyond_counting}`; each end `{index, q10, level}` (module docstring),
    null numbers without birds."""
    sums = edge_sums(days, effort, c, first_year, last_year)
    out = {"method": METHOD}
    if not len(sums) or sums["b"].sum() <= 0:
        return (
            out
            | {e: {"index": None, "q10": None, "level": None} for e in ("early", "late")}
            | {"beyond_counting": []}
        )
    a = sums.to_numpy()
    draws = a[np.random.default_rng(SEED).integers(0, len(a), (DRAWS, len(a)))].sum(axis=1)
    for end in ("early", "late"):
        index = float(_index(a.sum(axis=0), end, sums.columns))
        q10 = float(np.nanquantile(_index(draws, end, sums.columns), EDGE_QUANTILE))
        index, q10 = (None if np.isnan(x) else x for x in (index, q10))
        level = (
            "consistent"
            if q10 is not None and q10 >= EDGE_INDEX
            else "some_years"
            if index is not None and index >= EDGE_INDEX
            else None
        )
        out[end] = {
            "index": None if index is None else round(index, 2),
            "q10": None if q10 is None else round(q10, 2),
            "level": level,
        }
    out["beyond_counting"] = [e for e in ("early", "late") if out[e]["level"] == "consistent"]
    return out
