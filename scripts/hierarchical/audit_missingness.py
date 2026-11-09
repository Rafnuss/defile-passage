"""Audit why days and hours of the counting season are missing (step 1, no model fitted).

Run from the repository root:
uv run --with 'pyarrow<20' python scripts/hierarchical/audit_missingness.py
  > logs/hierarchical/audit.log

Four questions, all from the release, the frozen historical counts and the ERA5 cache:

1. Days: which season days have no count, by era, month, weekday and daylight weather.
2. Hours: on counted days, which daylight hours are not counted, by time of day, era and the
   hour's weather; and how late counting starts and how early it ends.
3. Early ends and late starts: on days timed to the hour, is the last counted hour before an early
   end quieter than the same hour on days that go on (observers leave when passage dies down)? A
   late start is the control: observers arriving cannot know the passage before.
4. Whole missing days: is passage on the days either side of a missing day lower than its local
   level, compared with the days either side of a counted day?
"""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage import hourly as H
from defile_passage.release import TIMEZONE, TREKTELLEN_ERA, civil_twilight, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/raw/dataset"
HISTORICAL = ROOT / "logs/historical-counts/observations.csv"
CACHE = ROOT.parent / "defile-migration-forecast/data/weather/era5_hourly/location=Defile"
OUT = ROOT / "logs/hierarchical/audit"
OUT.mkdir(parents=True, exist_ok=True)
CORE = pd.read_csv(ROOT / "scripts/research/historical_core_scope.tsv", sep="\t")["english_name"]

YEARS = (1993, 2025)
SEASON_DOY = (196, 319)  # 15 Jul - 15 Nov (non-leap), cut to each year's first and last count
ERAS = (  # (era, first year): the recording conventions of the release
    ("notebook", 1993),
    ("spreadsheet", 2014),
    ("naturalist", 2017),
    ("trektellen", 2022),
)
HOURLY_FROM = 2014  # counts timed to the hour from here on
WET_MM = 0.1  # an hour with at least this rain is wet
DRY_DAY_MM = 0.5  # a day with less daylight rain is dry
FULL_SLOT = 0.9  # an hour counted for at least this share of its daylight is fully counted
EARLY_HOURS = 2  # an end (start) this many hours or more before dusk (after dawn) is early (late)
RUN_HOURS = 3  # fully counted hours before the last (after the first) that set its expectation
NEIGHBOUR_DAYS = 7  # days either side that set a day's local passage level
MIN_DAY_HOURS = 6  # hours counted for a day to set or receive a local level
BOOT = 500
rng = np.random.default_rng(1)


def era_of(year):
    return pd.cut(
        year,
        [y for _, y in ERAS] + [YEARS[1] + 1],
        right=False,
        labels=[e for e, _ in ERAS],
    ).astype(str)


def split_hours(intervals: pd.DataFrame) -> pd.DataFrame:
    """Intervals (`start`, `end`, UTC) split at hour boundaries: `slot_start` and hours inside."""
    rows = []
    for key, start, end in intervals[["key", "start", "end"]].itertuples(index=False):
        edges = [start, *pd.date_range(start.ceil("h"), end, freq="h"), end]
        rows += [
            (key, a.floor("h"), (b - a) / pd.Timedelta(hours=1))
            for a, b in zip(edges, edges[1:])
            if b > a
        ]
    return pd.DataFrame(rows, columns=["key", "slot_start", "hours"])


def logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1e-4) -> np.ndarray:
    """Logistic regression coefficients by Newton steps (a small ridge keeps empty cells
    finite)."""
    b = np.zeros(X.shape[1])
    for _ in range(100):
        p = 1 / (1 + np.exp(-(X @ b)))
        hess = X.T @ (X * (p * (1 - p))[:, None]) + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(hess, X.T @ (y - p) - ridge * b)
        b += step
        if np.abs(step).max() < 1e-9:
            break
    return b


def odds_table(frame: pd.DataFrame, y: str, terms: list[str], cluster: str) -> pd.DataFrame:
    """Odds ratios of `terms` (numeric columns, continuous ones standardised by the caller) with
    95% intervals from a bootstrap over `cluster` (days or years: rows within one are not
    independent)."""
    X = np.column_stack([np.ones(len(frame)), frame[terms].to_numpy(float)])
    target = frame[y].to_numpy(float)
    coef = logistic(X, target)
    groups = frame.groupby(cluster).indices
    keys = np.array(list(groups))
    boots = []
    for _ in range(BOOT // 5):  # Newton fits of tens of thousands of rows: fewer draws
        pick = np.concatenate([groups[k] for k in rng.choice(keys, len(keys))])
        boots.append(logistic(X[pick], target[pick]))
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return pd.DataFrame(
        {"term": terms, "odds_ratio": np.exp(coef[1:]), "lo": np.exp(lo[1:]), "hi": np.exp(hi[1:])}
    )


def show(title: str, table: pd.DataFrame, name: str) -> None:
    table.to_csv(OUT / f"{name}.csv", index=False)
    print(f"\n## {title}\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.3g}"))


# Season grid of daylight hours ----------------------------------------------------------------
surveys = parse_surveys(pd.read_csv(DATASET / "survey.csv", low_memory=False))
surveys = surveys[surveys.date.dt.year.between(*YEARS)].copy()
counted = surveys[surveys.survey_complete.eq(True) & ~surveys.weather_stop.eq(True)]
closed = surveys[surveys.weather_stop.eq(True)]
span = counted.groupby(counted.date.dt.year)["date"].agg(["min", "max"])
dates = []
for year, (first, last) in span.iterrows():
    days = pd.Series(pd.date_range(first, last))
    d = days.dt.dayofyear - (days.dt.is_leap_year & days.dt.month.gt(2))
    dates.append(days[d.between(*SEASON_DOY)])
dates = pd.concat(dates, ignore_index=True)
dawn, dusk = civil_twilight(dates)
days = pd.DataFrame({"date": dates, "dawn": dawn, "dusk": dusk})
days["year"] = days.date.dt.year
days["era"] = era_of(days.year)
days["month"] = days.date.dt.month
days["weekend"] = days.date.dt.dayofweek.ge(5)
days["daylight_hours"] = (days.dusk - days.dawn) / pd.Timedelta(hours=1)

slots = []
for row in days.itertuples():
    for s in pd.date_range(row.dawn.floor("h"), row.dusk, freq="h"):
        a, b = max(s, row.dawn), min(s + pd.Timedelta(hours=1), row.dusk)
        if b > a:
            slots.append((row.date, s, (b - a) / pd.Timedelta(hours=1)))
slots = pd.DataFrame(slots, columns=["date", "slot_start", "daylight"])
slots = slots.merge(days, on="date", validate="many_to_one")
slots["tau"] = (slots.slot_start + pd.Timedelta(minutes=30) - slots.dawn) / (
    slots.dusk - slots.dawn
)


def slot_cover(intervals: pd.DataFrame) -> pd.Series:
    """Hours of each grid slot inside the intervals, clipped to its daylight."""
    clip = intervals.copy()
    clip["key"] = range(len(clip))
    clip["day"] = clip.start.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
    clip = clip.merge(days[["date", "dawn", "dusk"]], left_on="day", right_on="date")
    clip["start"] = clip[["start", "dawn"]].max(axis=1)
    clip["end"] = clip[["end", "dusk"]].min(axis=1)
    pieces = split_hours(clip[clip.end > clip.start])
    cover = pieces.groupby("slot_start")["hours"].sum()
    return slots.slot_start.map(cover).fillna(0).clip(upper=slots.daylight)


slots["counted"] = slot_cover(counted[["start", "end"]])
slots["closed"] = slot_cover(closed[["start", "end"]])

# Weather: as the research's hourly builder (rain at t+1 describes [t, t+1)) ------------------
parts = [
    p for p in sorted(CACHE.glob("part-*.parquet")) if YEARS[0] - 5 <= int(p.stem[5:]) <= YEARS[1]
]
columns = ["total_precipitation", "u_component_of_wind_10m", "v_component_of_wind_10m"]
columns += ["low_cloud_cover", "surface_solar_radiation_downwards"]
weather = pd.concat([pd.read_parquet(p, columns=["datetime", *columns]) for p in parts])
weather.index = pd.to_datetime(weather.pop("datetime"), utc=True)
weather = weather.sort_index().asfreq("h")
w = pd.DataFrame(index=weather.index)
w["rain_mm"] = weather.total_precipitation.shift(-1) * 1000
w["rain_previous_3h_mm"] = w.rain_mm.shift(1).rolling(3).sum()
w["radiation_w_m2"] = weather.surface_solar_radiation_downwards.shift(-1) / 3600
for source, target in (
    ("u_component_of_wind_10m", "wind_u"),
    ("v_component_of_wind_10m", "wind_v"),
    ("low_cloud_cover", "low_cloud"),
):
    w[target] = (weather[source] + weather[source].shift(-1)) / 2
w["wind_speed"] = np.hypot(w.wind_u, w.wind_v)
slots = slots.join(w, on="slot_start")
assert slots.rain_mm.notna().all(), "ERA5 cache does not cover the season grid"
slots["wet"] = slots.rain_mm.ge(WET_MM)

# Day status and daylight weather --------------------------------------------------------------
day = slots.groupby("date").agg(
    counted_hours=("counted", "sum"),
    closed_hours=("closed", "sum"),
    rain_mm=("rain_mm", "sum"),
    wet_fraction=("wet", "mean"),
    wind_speed=("wind_speed", "mean"),
    wind_u=("wind_u", "mean"),
    wind_v=("wind_v", "mean"),
    low_cloud=("low_cloud", "mean"),
    radiation_w_m2=("radiation_w_m2", "mean"),
)
days = days.merge(day, left_on="date", right_index=True, validate="one_to_one")
days["status"] = np.select(
    [days.counted_hours.gt(0), days.closed_hours.gt(0)],
    ["counted", "closed"],
    "uncounted",
)
days["missing"] = days.status.ne("counted")
days["rain_class"] = pd.cut(
    days.rain_mm, [-1, DRY_DAY_MM, 5, np.inf], labels=["dry <0.5mm", "0.5-5mm", "wet >5mm"]
).astype(str)

show(
    "1a. Season days by status and era",
    days.groupby("era", sort=False)
    .agg(
        days=("date", "size"),
        counted=("status", lambda s: s.eq("counted").mean()),
        closed_documented=("status", lambda s: s.eq("closed").mean()),
        uncounted=("status", lambda s: s.eq("uncounted").mean()),
        counted_hours_mean=("counted_hours", lambda s: s[s > 0].mean()),
        daylight_hours=("daylight_hours", "mean"),
    )
    .reset_index(),
    "days_by_era",
)
show(
    "1b. Share of season days missing, by era and daylight rain",
    days.pivot_table("missing", "era", "rain_class", sort=False).reset_index(),
    "missing_by_rain",
)
show(
    "1c. Share of season days missing, by era and month",
    days.pivot_table("missing", "era", "month", sort=False).reset_index(),
    "missing_by_month",
)
show(
    "1d. Share of season days missing, by era, weekday and weekend",
    days.pivot_table("missing", "era", "weekend", sort=False).reset_index(),
    "missing_by_weekend",
)

model = days.copy()
continuous = ["log_rain", "wet_fraction", "wind_speed", "low_cloud", "radiation_w_m2"]
model["log_rain"] = np.log1p(model.rain_mm)
model[continuous] = (model[continuous] - model[continuous].mean()) / model[continuous].std()
dummies = pd.get_dummies(model[["era", "month"]].astype(str), drop_first=True, dtype=float)
model = pd.concat([model, dummies], axis=1)
model["weekend"] = model.weekend.astype(float)
model["missing"] = model.missing.astype(float)
show(
    "1e. Odds of a missing day (per SD of each weather term; era, month, weekend adjusted)",
    odds_table(model, "missing", continuous + ["weekend", *dummies.columns], "year"),
    "missing_day_odds",
)

# Hours of counted days ------------------------------------------------------------------------
hours = slots[slots.date.isin(days.date[days.status.eq("counted")])].copy()
hours["uncounted"] = hours.counted.lt(FULL_SLOT * hours.daylight)
hours["tau_bin"] = pd.cut(hours.tau, np.linspace(0, 1, 11), labels=False, include_lowest=True)
show(
    "2a. Share of daylight hours not counted on counted days, by era and tenth of daylight",
    hours.pivot_table("uncounted", "era", "tau_bin", sort=False).reset_index(),
    "uncounted_by_tau",
)
show(
    "2b. Share of daylight hours not counted on counted days, wet and dry hours, by era",
    hours.pivot_table("uncounted", "era", "wet", sort=False).reset_index(),
    "uncounted_by_wet",
)
first = hours[~hours.uncounted].groupby("date").slot_start.agg(["min", "max"])
ends = days.set_index("date").join(first, how="inner")
ends["late_start_h"] = ((ends["min"] - ends.dawn) / pd.Timedelta(hours=1)).clip(lower=0)
ends["early_end_h"] = ((ends.dusk - ends["max"]) / pd.Timedelta(hours=1) - 1).clip(lower=0)
show(
    "2c. Hours from dawn to the first fully counted hour and from the last to dusk (median)",
    ends.groupby(["era", "rain_class"], sort=False)[["late_start_h", "early_end_h"]]
    .median()
    .reset_index(),
    "start_end_by_rain",
)

hmodel = hours[hours.era.ne("notebook")].copy()  # notebook days are one interval: no inner gaps
hmodel["log_rain"] = np.log1p(hmodel.rain_mm)
hmodel["log_rain_previous_3h"] = np.log1p(hmodel.rain_previous_3h_mm)
hterms = ["log_rain", "log_rain_previous_3h", "wind_speed", "low_cloud"]
hmodel[hterms] = (hmodel[hterms] - hmodel[hterms].mean()) / hmodel[hterms].std()
hd = pd.get_dummies(hmodel[["era", "tau_bin", "month"]].astype(str), drop_first=True, dtype=float)
hmodel = pd.concat([hmodel, hd], axis=1)
hmodel["uncounted"] = hmodel.uncounted.astype(float)
show(
    "2d. Odds of an uncounted hour on a counted day, 2014-2025 (era, daylight tenth, month)",
    odds_table(hmodel, "uncounted", hterms, "date").query("term in @hterms"),
    "uncounted_hour_odds",
)

# Hourly counts of the core species ------------------------------------------------------------
hist = pd.read_csv(HISTORICAL, low_memory=False, parse_dates=["start", "end"])
hist = hist[hist.training_eligible & hist.english_name.isin(CORE)]
hist["date"] = pd.to_datetime(hist.date)
daily_hist = hist.groupby(["english_name", "date"])["count"].sum()
hourly_hist = hist[
    (hist.year >= HOURLY_FROM)
    & hist.start.dt.floor("h").eq((hist.end - pd.Timedelta(seconds=1)).dt.floor("h"))
]
# A species-day is timed to the hour only when all of its records are.
whole = hist[hist.year >= HOURLY_FROM].groupby(["english_name", "date"]).size()
timed = hourly_hist.groupby(["english_name", "date"]).size()
timed_days = timed[timed.eq(whole.reindex(timed.index))].index
hourly_hist = hourly_hist.assign(slot_start=hourly_hist.start.dt.floor("h"))
hourly_hist = hourly_hist.set_index(["english_name", "date"]).loc[
    lambda f: f.index.isin(timed_days)
]
hourly_hist = (
    hourly_hist.reset_index().groupby(["english_name", "date", "slot_start"])["count"].sum()
)

taxonomy = pd.read_csv(DATASET / "taxonomy.csv")
taxa = taxonomy[taxonomy.english_name.isin(CORE)]
trek = surveys[surveys.recording_era.eq(TREKTELLEN_ERA)]
counts = pd.read_csv(DATASET / "count.csv", low_memory=False)
frame = H.species_hours(H.survey_hours(trek), H.count_timing(counts, trek), taxa)
frame["date"] = pd.to_datetime(frame.date)
complete = frame.groupby(["english_name", "date"]).hourly_complete.all()
frame = frame[frame.set_index(["english_name", "date"]).index.isin(complete[complete].index)]
hourly_trek = frame.groupby(["english_name", "date", "slot_start"])["count"].sum()
daily_trek = frame.groupby(["english_name", "date"])["count"].sum()
hourly = pd.concat([hourly_hist, hourly_trek]).rename("count").reset_index()
daily = pd.concat([daily_hist, daily_trek]).rename("count").reset_index()
print(f"\nHourly species-days: {hourly.groupby(['english_name', 'date']).ngroups}")

# 3. Early ends and late starts ----------------------------------------------------------------
full = hours[~hours.uncounted][["date", "slot_start", "era", "month", "wet", "dawn", "dusk"]]
grid = full.merge(hourly, on=["date", "slot_start"]).sort_values(["english_name", "slot_start"])
grid["hour"] = grid.slot_start.dt.hour


def runs(direction: int) -> pd.DataFrame:
    """Each fully counted hour with its `RUN_HOURS` neighbours on one side (before for an end,
    after for a start), whether counting carries on past it on the other side, and whether it is
    the day's last (first) hour well before dusk (after dawn)."""
    g = grid.copy()
    by = g.groupby(["english_name", "date"])
    step = pd.Timedelta(hours=1)
    contiguous = pd.Series(True, index=g.index)
    run = pd.Series(0.0, index=g.index)
    for k in range(1, RUN_HOURS + 1):
        contiguous &= by.slot_start.shift(direction * k).eq(g.slot_start - direction * k * step)
        run += by["count"].shift(direction * k).fillna(0)
    g["run"] = run
    g["contiguous"] = contiguous
    after = by.slot_start.shift(-direction)
    g["goes_on"] = after.eq(g.slot_start + direction * step) & by.slot_start.shift(
        -2 * direction
    ).eq(g.slot_start + 2 * direction * step)
    edge = after.isna()
    if direction > 0:  # an end: the last counted hour, well before dusk
        g["edge"] = edge & ((g.dusk - g.slot_start) / step - 1).ge(EARLY_HOURS)
    else:  # a start: the first counted hour, well after dawn
        g["edge"] = edge & ((g.slot_start - g.dawn) / step).ge(EARLY_HOURS)
    return g[g.contiguous & (g.goes_on | g.edge)]


def poisson_weights(groups: pd.Series, n: int) -> np.ndarray:
    """Poisson bootstrap: one weight per group (day or year) and draw, spread to the rows."""
    codes, uniques = pd.factorize(groups)
    return rng.poisson(1.0, (n, len(uniques)))[:, codes]


def edge_ratios(g: pd.DataFrame) -> pd.DataFrame:
    """Counts in the edge hours over their expectation, per species with a bootstrap over days.

    The expectation of an edge hour is its preceding (following) `RUN_HOURS` hours' count times
    the ratio of the hour to those hours on days that go on, in the same species, era, month and
    clock hour. A stratum with no birds in those hours on any going-on day sets no expectation.
    Species are pooled equally: geometric mean of (observed + 0.5) / (expected + 0.5).
    """
    strata = ["english_name", "era", "month", "hour"]
    stratum = g.groupby(strata).ngroup().to_numpy()
    n = stratum.max() + 1
    species = g.english_name.to_numpy()
    names = np.unique(species)
    weights = np.vstack([np.ones(len(g)), poisson_weights(g.date, BOOT)])
    ref = g.goes_on.to_numpy()
    edge = g.edge.to_numpy()
    count, run = g["count"].to_numpy(float), g.run.to_numpy(float)
    rows = []
    for w in weights:
        ref_count = np.bincount(stratum, w * count * ref, n)
        ref_run = np.bincount(stratum, w * run * ref, n)
        ratio = np.divide(ref_count, ref_run, out=np.full(n, np.nan), where=ref_run > 0)[stratum]
        use = edge & np.isfinite(ratio)
        obs = pd.Series(w * count * use).groupby(species).sum()
        exp = pd.Series(np.where(use, w * run * np.nan_to_num(ratio), 0)).groupby(species).sum()
        oe = (obs + 0.5) / (exp + 0.5)
        rows.append({**oe.to_dict(), "all core": np.exp(np.log(oe).mean())})
    draws = pd.DataFrame(rows)
    out = pd.DataFrame(
        {
            "obs_over_exp": draws.iloc[0],
            "lo": draws.iloc[1:].quantile(0.025),
            "hi": draws.iloc[1:].quantile(0.975),
        }
    )
    out["edge_days"] = pd.Series(g[g.edge].groupby("english_name").date.nunique())
    out["edge_birds"] = pd.Series(g[g.edge].groupby("english_name")["count"].sum())
    out.loc["all core", ["edge_days", "edge_birds"]] = [
        g[g.edge].date.nunique(),
        g[g.edge]["count"].sum(),
    ]
    return out.loc[["all core", *names]].rename_axis("species").reset_index()


tables = []
for name, direction in (("early end", 1), ("late start", -1)):
    g = runs(direction)
    for label, sub in (("all", g), ("dry edge hour", g[(g.edge & ~g.wet) | g.goes_on])):
        tables.append(edge_ratios(sub).assign(edge=name, weather=label))
show(
    "3. Observed / expected count in the last hour before an early end (first after a late start)",
    pd.concat(tables)[
        ["edge", "weather", "species", "obs_over_exp", "lo", "hi", "edge_days", "edge_birds"]
    ],
    "edge_hours",
)

# 4. Passage either side of a whole missing day ------------------------------------------------
level = daily.merge(days[["date", "counted_hours"]], on="date")
level = level[level.counted_hours.ge(MIN_DAY_HOURS)]
rows = []
for species, s in level.groupby("english_name"):
    s = s.set_index("date")
    for target in days.itertuples():
        gap = (s.index - target.date).days
        near = s[abs(gap) == 1]
        window = s[(abs(gap) <= NEIGHBOUR_DAYS) & (abs(gap) > 1)]
        if near.empty or len(window) < 4 or window["count"].sum() == 0:
            continue
        local = window["count"].sum() / window.counted_hours.sum()
        rows.append(
            (
                species,
                target.date,
                target.year,
                target.era,
                target.status,
                target.rain_mm < DRY_DAY_MM,
                near["count"].sum(),
                local * near.counted_hours.sum(),
            )
        )
nb = pd.DataFrame(
    rows, columns=["species", "date", "year", "era", "status", "dry", "observed", "expected"]
)


def neighbour_ratios(f: pd.DataFrame, missing: list[str]) -> dict:
    """(Observed / expected beside a missing day) over (the same beside a counted day), per
    species, then their geometric mean; with a bootstrap over years."""
    target = f.status.isin(missing).to_numpy()
    control = f.status.eq("counted").to_numpy()
    species = f.species.to_numpy()
    weights = np.vstack([np.ones(len(f)), poisson_weights(f.year, BOOT)])
    draws = []
    for w in weights:
        sums = (
            pd.DataFrame(
                {
                    "o_t": w * f.observed * target,
                    "e_t": w * f.expected * target,
                    "o_c": w * f.observed * control,
                    "e_c": w * f.expected * control,
                }
            )
            .groupby(species)
            .sum()
        )
        ratio = ((sums.o_t + 0.5) / (sums.e_t + 0.5)) / ((sums.o_c + 0.5) / (sums.e_c + 0.5))
        draws.append(np.exp(np.log(ratio[sums.e_t > 0]).mean()))
    return {
        "ratio": draws[0],
        "lo": np.nanpercentile(draws[1:], 2.5),
        "hi": np.nanpercentile(draws[1:], 97.5),
        "missing_days": f.date[target].nunique(),
    }


rows = []
for status_label, missing in (("missing", ["uncounted", "closed"]), ("uncounted", ["uncounted"])):
    for era_label, e in (
        ("all", nb),
        ("1993-2013", nb[nb.era.eq("notebook")]),
        ("2014-2025", nb[nb.era.ne("notebook")]),
    ):
        for dry_label, f in (("all", e), ("dry", e[e.dry]), ("wet", e[~e.dry])):
            if f.status.isin(missing).any():
                rows.append(
                    {"target": status_label, "era": era_label, "target_day": dry_label}
                    | neighbour_ratios(f, missing)
                )
show(
    "4. Passage either side of a missing day over its local level, against a counted day",
    pd.DataFrame(rows),
    "neighbour_days",
)
days.to_csv(OUT / "days.csv", index=False)
# Shared with the masks (`realistic_masks.py`).
slots.drop(columns=["dawn", "dusk"]).to_csv(OUT / "slots.csv", index=False)
hourly.to_csv(OUT / "hourly_counts.csv", index=False)
daily.to_csv(OUT / "daily_counts.csv", index=False)
