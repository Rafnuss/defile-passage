"""Inventory actual effort against a fixed comparison season; never infer bird zeros."""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage.export import in_window
from defile_passage.release import NIGHT_SUN_ALTITUDE, SITE, get_position, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/gap-target-audit"
OUT.mkdir(exist_ok=True)

# Fixed site comparison window, independent of first/last bird or survey dates.
surveys = parse_surveys(
    pd.read_csv(ROOT.parent / "defile-dataset/output/dataset/survey.csv", low_memory=False)
)
calendar = pd.DataFrame({"date": pd.date_range("1966-01-01", "2025-12-31")})
calendar = calendar[in_window(calendar.date)].copy()
# Both civil boundaries at this site lie within the UTC date; avoid ambiguous 1976 midnight.
midnight = pd.DatetimeIndex(calendar.date).tz_localize("UTC")
minutes = np.arange(24 * 60).astype("timedelta64[m]")
grid = pd.DatetimeIndex((midnight.values[:, None] + minutes[None, :]).ravel())
light = (
    np.degrees(np.asarray(get_position(grid, SITE[1], SITE[0])["altitude"])).reshape(
        len(calendar), -1
    )
    >= NIGHT_SUN_ALTITUDE
)
calendar["dawn"] = midnight + pd.to_timedelta(light.argmax(axis=1), unit="min")
calendar["dusk"] = midnight + pd.to_timedelta(1440 - light[:, ::-1].argmax(axis=1), unit="min")
calendar["daylight_hours"] = (calendar.dusk - calendar.dawn).dt.total_seconds() / 3600
rows = surveys.merge(calendar, on="date")
rows["observed"] = rows.survey_complete.eq(True) & ~rows.weather_stop.eq(True)
rows["hours"] = (rows.end - rows.start).dt.total_seconds() / 3600
rows["daylight_observed"] = (
    ((rows.end.clip(upper=rows.dusk) - rows.start.clip(lower=rows.dawn)).dt.total_seconds() / 3600)
    .clip(lower=0)
    .where(rows.observed, 0)
)
# Released intervals do not overlap; weather stops and incomplete sessions are excluded.
daily = rows.groupby("date", as_index=False).agg(
    observed_hours=("hours", lambda x: x[rows.loc[x.index, "observed"]].sum()),
    daylight_observed=("daylight_observed", "sum"),
    weather_stop=("weather_stop", lambda x: x.eq(True).any()),
    incomplete=("survey_complete", lambda x: x.eq(False).any()),
)
daily = calendar.merge(daily, on="date", how="left")
daily[["observed_hours", "daylight_observed"]] = daily[
    ["observed_hours", "daylight_observed"]
].fillna(0)
daily[["weather_stop", "incomplete"]] = daily[["weather_stop", "incomplete"]].eq(True)
daily["year"] = daily.date.dt.year
daily["coverage"] = daily.daylight_observed / daily.daylight_hours
daily["no_observed_effort"] = daily.observed_hours.eq(0)
daily["positive_below_half"] = daily.observed_hours.gt(0) & daily.coverage.lt(0.5)
daily["half_to_three_quarters"] = daily.coverage.ge(0.5) & daily.coverage.lt(0.75)
daily["at_least_three_quarters"] = daily.coverage.ge(0.75)
daily["era"] = pd.cut(
    daily.year,
    [1965, 1992, 2007, 2013, 2016, 2021, 2025],
    labels=["1966–1992", "1993–2007", "2008–2013", "2014–2016", "2017–2021", "2022–2025"],
)
daily.drop(columns=["dawn", "dusk"]).to_csv(OUT / "daily.csv", index=False)
for group in ["year", "era"]:
    summary = daily.groupby(group, observed=True).agg(
        calendar_days=("date", "size"),
        observed_hours=("observed_hours", "sum"),
        daylight_hours=("daylight_hours", "sum"),
        daylight_observed=("daylight_observed", "sum"),
        no_observed_days=("no_observed_effort", "sum"),
        observed_below_half=("positive_below_half", "sum"),
        half_to_three_quarters=("half_to_three_quarters", "sum"),
        at_least_three_quarters=("at_least_three_quarters", "sum"),
        documented_weather_days=("weather_stop", "sum"),
        incomplete_days=("incomplete", "sum"),
    )
    summary["daylight_effort_fraction"] = summary.daylight_observed / summary.daylight_hours
    summary.to_csv(OUT / f"{group}.csv")
    print(summary.to_string() if group == "era" else summary.loc[2022:2025].to_string())

# Current validation denominator: species-cases, not independent site-days.
short = pd.read_csv(ROOT / "logs/short-gaps-review/predictions.csv")
short = short[short.assessment_group.eq("core_large_birds") & short.method.eq("retained_in_fit")]
short.groupby(["year", "retained_coverage"]).agg(
    cases=("count", "size"), dates=("date", "nunique")
).to_csv(OUT / "short_gap_year_coverage.csv")
print("\nShort-gap core species-cases:")
print(short.retained_coverage.value_counts().to_string())
weather = pd.read_csv(ROOT / "data/hourly-weather-priority/weather_hourly.csv")
print(
    "\nCurrent research weather input:", weather.slot_start.min(), "to", weather.slot_start.max()
)
assert np.all(daily.daylight_observed <= daily.daylight_hours + 1e-8)
assert np.all(daily.coverage.between(0, 1 + 1e-8))
