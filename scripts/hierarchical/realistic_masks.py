"""Draw realistic assessment masks: counted days and hours hidden the way real gaps happen.

Run after `audit_missingness.py`, from the repository root:
uv run python scripts/hierarchical/realistic_masks.py > logs/hierarchical/masks.log

Two kinds (README "Missing hours and days are not random"), one set of dates for all species:

- Day masks, 1993-2025: a counted day is hidden with the chance of a real missing day, from a
  logistic model fitted on every season day: era, month, weekend, daylight rain and radiation,
  the passage of the days either side against their local level, and whether the day before is
  missing (runs). The intercept of each era is shifted so that every era hides `DAY_SHARE` of its
  eligible days: the selection follows the real one, the number is raised for the assessment.
- Early-end masks, 2014-2025: a full day timed to the hour is ended early with the hazard of a real
  early end, fitted on the afternoon hours of the real days: era, month, time of day, rain in the
  hour and the three before, and the passage of the last three hours against their usual level.
  The intercept is shifted so that `END_SHARE` of the eligible days end early.

Eligible days are counted for at least `MIN_DAY_HOURS` and outside the lockbox. Writes one table
per draw (`date`, `kind`, `hide_from`) and the checks of what the masks hide.
"""

import numpy as np
import pandas as pd
from common import AUDIT, CORE, MASKS, in_lockbox, logistic
from scipy.optimize import brentq

DRAWS = 5
DAY_SHARE = 0.10
END_SHARE = 0.30
MIN_DAY_HOURS = 6
FULL_SLOT = 0.9  # as the audit
EARLY_HOURS = 2  # an end this many hours or more before dusk is early
FULL_DAY_MARGIN = 1.5  # a full day is counted to within this many hours of dusk
RISK_TAU = 0.4  # an early end is looked for from this point of the daylight on
NEIGHBOUR_DAYS = 7
HOURLY_FROM = 2014
MASKS.mkdir(parents=True, exist_ok=True)

days = pd.read_csv(AUDIT / "days.csv", parse_dates=["date"])
for column in ("dawn", "dusk"):
    days[column] = pd.to_datetime(days[column], utc=True)
slots = pd.read_csv(AUDIT / "slots.csv", parse_dates=["date"])
slots["slot_start"] = pd.to_datetime(slots.slot_start, utc=True)
daily = pd.read_csv(AUDIT / "daily_counts.csv", parse_dates=["date"])
hourly = pd.read_csv(AUDIT / "hourly_counts.csv", parse_dates=["date"])
hourly["slot_start"] = pd.to_datetime(hourly.slot_start, utc=True)
days = days.sort_values("date").reset_index(drop=True)


def standardise(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return (frame[columns] - frame[columns].mean()) / frame[columns].std()


# Passage either side of each day against its local level (audit section 4) -------------------
level = daily.merge(days[["date", "counted_hours"]], on="date")
level = level[level.counted_hours.ge(MIN_DAY_HOURS)]
index = []
for species, s in level.groupby("english_name"):
    s = s.set_index("date")
    for target in days.date:
        gap = (s.index - target).days
        near = s[abs(gap) == 1]
        window = s[(abs(gap) <= NEIGHBOUR_DAYS) & (abs(gap) > 1)]
        if near.empty or len(window) < 4 or window["count"].sum() == 0:
            continue
        expected = window["count"].sum() / window.counted_hours.sum() * near.counted_hours.sum()
        index.append((target, np.log((near["count"].sum() + 0.5) / (expected + 0.5))))
index = pd.DataFrame(index, columns=["date", "passage"]).groupby("date").passage.mean()
days["passage"] = days.date.map(index).fillna(0)
days["previous_missing"] = days.missing.shift().where(days.date.diff().dt.days.eq(1), False)

# Day masks ------------------------------------------------------------------------------------
day_terms = ["log_rain", "wet_fraction", "radiation_w_m2", "passage"]
X_day = days.assign(log_rain=np.log1p(days.rain_mm))
X_day[day_terms] = standardise(X_day, day_terms)
dummies = pd.get_dummies(days[["era", "month"]].astype(str), dtype=float)
X_day = pd.concat(
    [
        X_day[day_terms],
        days[["weekend", "previous_missing"]].astype(float),
        dummies.drop(columns=["era_naturalist", "month_9"]),
    ],
    axis=1,
)
day_names = ["intercept", *X_day.columns]
X_day = np.column_stack([np.ones(len(days)), X_day.to_numpy(float)])
b_day = logistic(X_day, days.missing.to_numpy(float))
print("Day model (log odds):")
print(pd.Series(b_day, index=day_names).round(3).to_string())
previous = day_names.index("previous_missing")
days["day_eligible"] = (
    days.status.eq("counted") & days.counted_hours.ge(MIN_DAY_HOURS) & ~in_lockbox(days.date)
)
base = X_day @ b_day - b_day[previous] * X_day[:, previous]  # without the previous day
shift = {}
for era, rows in days[days.day_eligible].groupby("era").groups.items():
    linear = base[rows]
    shift[era] = brentq(lambda d: (1 / (1 + np.exp(-(linear + d)))).mean() - DAY_SHARE, -20, 20)
print("Era intercept shifts:", {k: round(v, 2) for k, v in shift.items()})
days["day_linear"] = base + days.era.map(shift)

# Early-end hazard -----------------------------------------------------------------------------
full = slots[slots.counted.ge(FULL_SLOT * slots.daylight) & slots.year.ge(HOURLY_FROM)].copy()
timed_days = hourly.date.unique()
full = full[full.date.isin(timed_days)].merge(days[["date", "dusk", "dawn"]], on="date")
full = full.sort_values("slot_start").reset_index(drop=True)
# Passage of the last three hours (the hour and the two before) against its usual level.
counts = hourly.pivot_table("count", ["date", "slot_start"], "english_name").reindex(
    columns=list(CORE)
)
log3 = np.log1p(
    counts.groupby(level="date").rolling(3, min_periods=3).sum().droplevel(0).sort_index()
)
log3 = log3.reset_index()
log3["month"], log3["hour"] = log3.date.dt.month, log3.slot_start.dt.hour
usual = log3.groupby(["month", "hour"])[list(CORE)].transform("mean")
log3["passage3"] = (log3[list(CORE)] - usual).mean(axis=1)
full = full.merge(log3[["slot_start", "passage3"]], on="slot_start", how="left")
step = pd.Timedelta(hours=1)
by = full.groupby("date").slot_start
full["last"] = by.shift(-1).isna()
full["contiguous3"] = by.shift(2).eq(full.slot_start - 2 * step)
full["risk"] = (
    full.tau.ge(RISK_TAU)
    & ((full.dusk - full.slot_start) / step - 1).ge(EARLY_HOURS)
    & full.contiguous3
    & full.passage3.notna()
)
risk = full[full.risk].copy()
risk["end"] = risk["last"].astype(float)
end_terms = ["log_rain", "log_rain_previous_3h", "passage3"]
risk["log_rain"] = np.log1p(risk.rain_mm)
risk["log_rain_previous_3h"] = np.log1p(risk.rain_previous_3h_mm)
stats = risk[end_terms].agg(["mean", "std"])
tau_bin = pd.cut(risk.tau, [0, 0.5, 0.6, 0.7, 0.8, 1], labels=list("abcde")).astype(str)
end_dummies = pd.get_dummies(
    pd.DataFrame({"era": risk.era, "month": risk.month.astype(str), "tau": tau_bin}), dtype=float
)
end_dummies = end_dummies.drop(columns=[end_dummies.columns[0], "month_9", "tau_a"])
X_end = pd.concat([(risk[end_terms] - stats.loc["mean"]) / stats.loc["std"], end_dummies], axis=1)
end_names = ["intercept", *X_end.columns]
b_end = logistic(np.column_stack([np.ones(len(risk)), X_end.to_numpy(float)]), risk.end.to_numpy())
print("\nEarly-end hazard (log odds, per SD for weather and passage):")
print(pd.Series(b_end, index=end_names).round(3).to_string())
risk["end_linear"] = np.column_stack([np.ones(len(risk)), X_end.to_numpy(float)]) @ b_end

# Full days: counted to within `FULL_DAY_MARGIN` of dusk, eligible for an early-end mask.
last = full.groupby("date").slot_start.max()
reach = (days.set_index("date").dusk - last.reindex(days.date).to_numpy() - step) / step
days["end_eligible"] = (
    days.date.isin(last.index)
    & reach.to_numpy().__le__(FULL_DAY_MARGIN)
    & days.status.eq("counted")
    & ~in_lockbox(days.date)
)
candidates = risk[risk.date.isin(days.date[days.end_eligible])]
groups = candidates.groupby("date").indices
linear = candidates.end_linear.to_numpy()


def end_share(d: float) -> float:
    p = 1 / (1 + np.exp(-(linear + d)))
    survive = np.array([np.prod(1 - p[i]) for i in groups.values()])
    return 1 - survive.mean() * len(groups) / days.end_eligible.sum() - END_SHARE


end_shift = brentq(end_share, -20, 20)
print(f"\nEarly-end intercept shift {end_shift:.2f}, eligible days {days.end_eligible.sum()}")

# Draws ----------------------------------------------------------------------------------------
checks = []
for draw in range(DRAWS):
    rng = np.random.default_rng(100 + draw)
    hidden = np.zeros(len(days), bool)
    for i in np.flatnonzero(days.day_eligible):
        run = i > 0 and hidden[i - 1] and (days.date[i] - days.date[i - 1]).days == 1
        p = 1 / (1 + np.exp(-(days.day_linear[i] + run * b_day[previous])))
        hidden[i] = rng.random() < p
    mask = [days.loc[hidden, ["date"]].assign(kind="day", hide_from=pd.NaT)]
    ends = []
    for date, rows in groups.items():
        if hidden[days.index[days.date.eq(date)][0]]:
            continue
        p = 1 / (1 + np.exp(-(linear[rows] + end_shift)))
        hit = np.flatnonzero(rng.random(len(rows)) < p)
        if len(hit):
            ends.append((date, candidates.slot_start.iloc[rows[hit[0]]] + step))
    mask.append(pd.DataFrame(ends, columns=["date", "hide_from"]).assign(kind="end"))
    mask = pd.concat(mask, ignore_index=True)[["date", "kind", "hide_from"]]
    mask.to_csv(MASKS / f"draw{draw}.csv", index=False)
    d = days.assign(hidden=hidden)
    ended = d.date.isin(mask.date[mask.kind.eq("end")])
    for era, e in d.groupby("era", sort=False):
        checks.append(
            {
                "draw": draw,
                "era": era,
                "eligible_days": int(e.day_eligible.sum()),
                "hidden_days": int(e.hidden.sum()),
                "end_eligible": int(e.end_eligible.sum()),
                "ended_early": int(ended[e.index].sum()),
            }
        )
    hidden_ends = mask[mask.kind.eq("end")].merge(days[["date", "dusk"]], on="date")
    print(
        f"draw {draw}: {hidden.sum()} days hidden, {len(hidden_ends)} ended early, median "
        f"{((hidden_ends.dusk - hidden_ends.hide_from) / step).median():.1f} h before dusk"
    )

checks = pd.DataFrame(checks)
checks.to_csv(MASKS / "checks_share.csv", index=False)
print("\nHidden days and early ends per era (mean over draws):")
print(checks.groupby("era", sort=False).mean().drop(columns="draw").round(1).to_string())

# What the masks hide, against real gaps and all eligible days --------------------------------
masks = pd.concat(
    [
        pd.read_csv(MASKS / f"draw{k}.csv", parse_dates=["date"]).assign(draw=k)
        for k in range(DRAWS)
    ]
)
masks["hide_from"] = pd.to_datetime(masks.hide_from, utc=True)
masked = days[days.date.isin(masks.date[masks.kind.eq("day")])]
groups_ = {
    "real missing days": days[days.missing],
    "eligible days": days[days.day_eligible],
    "masked days (all draws)": masked,
}
rows = []
for label, g in groups_.items():
    rows.append(
        {
            "days": label,
            "n": len(g),
            "rain_mm": g.rain_mm.mean(),
            "share >5mm": g.rain_mm.gt(5).mean(),
            "radiation": g.radiation_w_m2.mean(),
            "passage index": g.passage.mean(),
            "1993-2013": g.year.lt(2014).mean(),
            "November": g.month.eq(11).mean(),
        }
    )
table = pd.DataFrame(rows)
table.to_csv(MASKS / "checks_days.csv", index=False)
print("\nDays hidden against real missing days:")
print(table.to_string(index=False, float_format=lambda v: f"{v:.3g}"))

real_end = full[full["last"] & full.risk].merge(days[["date"]], on="date")
mask_end = masks[masks.kind.eq("end")].merge(days[["date", "dusk"]], on="date")
ends = pd.DataFrame(
    {
        "ends": ["real early ends", "masked early ends"],
        "n": [len(real_end), len(mask_end)],
        "hours_before_dusk": [
            ((real_end.dusk - real_end.slot_start) / step - 1).median(),
            ((mask_end.dusk - mask_end.hide_from) / step).median(),
        ],
        "passage3": [
            real_end.passage3.mean(),
            risk.set_index("slot_start").passage3.reindex(mask_end.hide_from - step).mean(),
        ],
        "rain_previous_3h_mm": [
            real_end.rain_previous_3h_mm.mean(),
            risk.set_index("slot_start")
            .rain_previous_3h_mm.reindex(mask_end.hide_from - step)
            .mean(),
        ],
    }
)
ends.loc[2] = [
    "all risk hours",
    len(risk),
    np.nan,
    risk.passage3.mean(),
    risk.rain_previous_3h_mm.mean(),
]
ends.to_csv(MASKS / "checks_ends.csv", index=False)
print("\nEarly ends of the masks against the real ones:")
print(ends.to_string(index=False, float_format=lambda v: f"{v:.3g}"))
days.to_csv(MASKS / "days.csv", index=False)
