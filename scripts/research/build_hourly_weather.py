"""Prepare a standalone Trektellen hourly weather pilot from release tables and an ERA5 cache.

Run from the repository root with uv run --with pyarrow==13.0.0 python
scripts/research/build_hourly_weather.py --dataset ../defile-dataset/output/dataset
--weather-cache ../defile-migration-forecast/data/weather/era5_hourly.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from defile_explore import hourly as H
from defile_explore.release import TREKTELLEN_ERA, civil_twilight, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
PILOT_TAXA = ("Red Kite", "Common Buzzard", "European Honey Buzzard", "Common Wood Pigeon")
WEATHER_COLUMNS = (
    "total_precipitation",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "low_cloud_cover",
    "surface_solar_radiation_downwards",
)

# Read the current release ---------------------------------------------------
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--weather-cache", type=Path, required=True)
parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
parser.add_argument("--taxa", nargs="+", default=PILOT_TAXA)
parser.add_argument(
    "--scope-table", type=Path, default=ROOT / "scripts/research/weather_species.tsv"
)
parser.add_argument("--out", type=Path, default=ROOT / "data/hourly-weather")
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
surveys = parse_surveys(pd.read_csv(args.dataset / "survey.csv", low_memory=False))
surveys = surveys[
    surveys["recording_era"].eq(TREKTELLEN_ERA) & surveys["date"].dt.year.isin(args.years)
].copy()
counts = pd.read_csv(args.dataset / "count.csv", low_memory=False)
taxonomy = pd.read_csv(args.dataset / "taxonomy.csv")
taxa = taxonomy[taxonomy["english_name"].isin(args.taxa)]
assert set(taxa["english_name"]) == set(args.taxa), "Taxon name absent from taxonomy"

# Split effort independently of bird entries ---------------------------------
hours = H.survey_hours(surveys)
timing = H.count_timing(counts, surveys)
timed = timing[timing["slot_start"].notna()]
unresolved = timing[timing["slot_start"].isna()]
assert timing["count"].sum() == timed["count"].sum() + unresolved["count"].sum()
observed = surveys[surveys["survey_complete"].eq(True) & ~surveys["weather_stop"].eq(True)]
expected_hours = ((observed["end"] - observed["start"]) / pd.Timedelta(hours=1)).sum()
assert abs(hours["exposure_hours"].sum() - expected_hours) < 1e-8
frame = H.recording_scope(
    H.species_hours(hours, timing, taxa), pd.read_csv(args.scope_table, sep="\t")
)
midpoint = frame["start"] + (frame["end"] - frame["start"]) / 2
dates = pd.to_datetime(frame["date"])
dawn, dusk = civil_twilight(dates)
frame["dawn"], frame["dusk"] = dawn, dusk
frame["tau"] = (midpoint - dawn) / (dusk - dawn)
frame["within_daylight"] = frame["start"].ge(dawn) & frame["end"].le(dusk)
frame["year"] = dates.dt.year
frame["doy"] = dates.dt.dayofyear - (dates.dt.is_leap_year & dates.dt.month.gt(2))

# Copy a bounded weather snapshot, with explicit units and interval alignment --
parts = sorted((args.weather_cache / "location=Defile").glob("part-*.parquet"))
parts = [
    p
    for p in parts
    if int(p.stem.split("-")[1]) <= max(args.years)
    and int(p.stem.split("-")[1]) + 4 >= min(args.years) - 1
]
weather = pd.concat([pd.read_parquet(p, columns=["datetime", *WEATHER_COLUMNS]) for p in parts])
weather["slot_start"] = pd.to_datetime(weather["datetime"], utc=True)
weather = weather.set_index("slot_start").sort_index()
weather = weather.reindex(pd.date_range(weather.index.min(), weather.index.max(), freq="h"))
weather.index.name = "slot_start"
# Open-Meteo accumulations at t describe [t-1h, t); slot_start labels [t, t+1h).
weather["rain_mm"] = weather["total_precipitation"].shift(-1) * 1000
weather["radiation_w_m2"] = weather["surface_solar_radiation_downwards"].shift(-1) / 3600
weather["rain_previous_24h_mm"] = weather["rain_mm"].shift(1).rolling(24, min_periods=24).sum()
# Instantaneous wind/cloud states are approximated by their two hourly endpoints' mean.
for source, target in (
    ("u_component_of_wind_10m", "wind_u_m_s"),
    ("v_component_of_wind_10m", "wind_v_m_s"),
    ("low_cloud_cover", "low_cloud_fraction"),
):
    weather[target] = (weather[source] + weather[source].shift(-1)) / 2
features = [
    "rain_mm",
    "rain_previous_24h_mm",
    "wind_u_m_s",
    "wind_v_m_s",
    "radiation_w_m2",
    "low_cloud_fraction",
]
weather = weather.loc[dawn.min().floor("h") : dusk.max().ceil("h"), features].reset_index()
frame = frame.merge(weather, on="slot_start", how="left", validate="many_to_one")
frame["weather_available"] = frame[features].notna().all(axis=1)
frame["model_eligible"] = (
    frame["hourly_complete"]
    & frame["within_daylight"]
    & frame["weather_available"]
    & frame["scope_available"]
)
masks = H.validation_masks(frame[frame["model_eligible"]])

# Weather support for observed and missing daylight hours, including documented closures.
season_dates = pd.concat(
    [
        pd.Series(pd.date_range(s["date"].min(), s["date"].max()))
        for _, s in surveys.groupby(surveys["date"].dt.year)
    ],
    ignore_index=True,
)
grid_dawn, grid_dusk = civil_twilight(season_dates)
grid_surveys = pd.DataFrame(
    {
        "survey_id": season_dates.dt.strftime("grid-%Y-%m-%d"),
        "recording_era": TREKTELLEN_ERA,
        "survey_complete": True,
        "weather_stop": False,
        "start": grid_dawn,
        "end": grid_dusk,
    }
)
prediction_hours = H.survey_hours(grid_surveys)
twilight = pd.DataFrame({"date": season_dates.dt.date, "dawn": grid_dawn, "dusk": grid_dusk})
prediction_hours = prediction_hours.merge(twilight, on="date", validate="many_to_one")
prediction_midpoint = (
    prediction_hours["start"] + (prediction_hours["end"] - prediction_hours["start"]) / 2
)
prediction_hours["tau"] = (prediction_midpoint - prediction_hours["dawn"]) / (
    prediction_hours["dusk"] - prediction_hours["dawn"]
)
prediction_dates = pd.to_datetime(prediction_hours["date"])
prediction_hours["year"] = prediction_dates.dt.year
prediction_hours["doy"] = prediction_dates.dt.dayofyear - (
    prediction_dates.dt.is_leap_year & prediction_dates.dt.month.gt(2)
)
prediction_hours = prediction_hours.merge(
    weather, on="slot_start", how="left", validate="many_to_one"
)
prediction_hours["documented_weather_stop"] = prediction_hours["date"].isin(
    surveys.loc[surveys["weather_stop"].eq(True), "date"].dt.date
)
prediction_hours["closure_exposure_hours"] = 0.0
for closure in surveys[surveys["weather_stop"].eq(True)].itertuples():
    on_day = prediction_hours["date"].eq(closure.date.date())
    overlap = prediction_hours.loc[on_day, "end"].clip(upper=closure.end) - prediction_hours.loc[
        on_day, "start"
    ].clip(lower=closure.start)
    prediction_hours.loc[on_day, "closure_exposure_hours"] += (
        overlap.dt.total_seconds().clip(lower=0) / 3600
    )
prediction_hours = prediction_hours.merge(taxa[["taxon_id", "english_name"]], how="cross")
observed_exposure = (
    frame[frame["model_eligible"]]
    .groupby(["english_name", "date", "slot_start"])["exposure_hours"]
    .sum()
    .rename("observed_exposure_hours")
)
prediction_hours = prediction_hours.merge(
    observed_exposure, on=["english_name", "date", "slot_start"], how="left"
)
prediction_hours["observed_exposure_hours"] = prediction_hours["observed_exposure_hours"].fillna(0)
prediction_hours["missing_exposure_hours"] = (
    prediction_hours["exposure_hours"] - prediction_hours["observed_exposure_hours"]
).clip(lower=0)

# Save the data and reconciliation -------------------------------------------
(args.out / "recording_scope.tsv").write_text(args.scope_table.read_text())
hours.to_csv(args.out / "hourly_effort.csv", index=False)
timed.groupby(["survey_id", "slot_start", "taxon_id"], as_index=False)["count"].sum().to_csv(
    args.out / "hourly_counts.csv", index=False
)
unresolved.drop(columns=["slot_start"]).to_csv(args.out / "unresolved_counts.csv", index=False)
surveys[surveys["weather_stop"].eq(True)].to_csv(args.out / "weather_stops.csv", index=False)
weather.to_csv(args.out / "weather_hourly.csv", index=False)
frame.to_csv(args.out / "model_frame.csv", index=False)
masks.to_csv(args.out / "validation_masks.csv", index=False)
prediction_hours.to_csv(args.out / "prediction_hours.csv", index=False)
reconciliation = timing.groupby("timing_status").agg(
    entries=("count_id", "size"), birds=("count", "sum")
)
reconciliation.to_csv(args.out / "timing_reconciliation.csv")
summary = frame.groupby("english_name").agg(
    intervals=("survey_id", "size"),
    eligible=("model_eligible", "sum"),
    timed_birds=("timed_count", "sum"),
    unknown_intervals=("unresolved_entries", lambda x: x.gt(0).sum()),
    missing_weather=("weather_available", lambda x: (~x).sum()),
)
summary.to_csv(args.out / "species_summary.csv")
sources = (
    [args.dataset / p for p in ("count.csv", "survey.csv", "taxonomy.csv")]
    + parts
    + [args.scope_table]
)
metadata = {
    "years": args.years,
    "taxa": list(args.taxa),
    "observed_hours": expected_hours,
    "source_birds": float(timing["count"].sum()),
    "timed_birds": float(timed["count"].sum()),
    "unresolved_birds": float(unresolved["count"].sum()),
    "sources": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    "weather_source": "Open-Meteo ERA5, Defile; bounded snapshot of the existing cache",
    "weather_interval_definition": "https://open-meteo.com/en/docs/historical-weather-api",
    "weather_alignment": "Rain/radiation at t+1h describe slot [t,t+1h); wind/cloud average endpoints",
    "assumptions": [
        "Zeros require explicitly accepted species recording scope and date range, in addition to complete effort",
        "Priority-target scope is documented in 2023-2025 reports; continuity in 2022 is assumed because its full report is unavailable",
        "Passerine recording throughout complete surveys in 2022-2025 was confirmed by the user on 2026-10-10; this is not extended to earlier years",
        "Untimed positive/presence entries invalidate that species' survey for hourly fitting",
        "Weather-stop assumed zeros are excluded from observed effort and model training",
        "The first model uses intervals wholly within civil dawn/dusk; other intervals remain in the export",
    ],
}
(args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(reconciliation.to_string())
print(summary.to_string())
print(f"Observed effort: {expected_hours:.2f} hours; output: {args.out}")
