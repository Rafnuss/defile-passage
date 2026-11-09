"""Keep either hourly counts or a whole-survey total, never both for one species.

Historical surveys are inventoried separately. Their absent species remain unknown: recent
recording-scope confirmation is not extended backwards automatically. Run with uv run python
scripts/research/prepare_mixed_intervals.py.
"""

import json
from pathlib import Path

import pandas as pd

from defile_passage import hourly as H
from defile_passage.release import (
    MAIN_CATEGORY,
    OUTSIDE_SURVEY_REMARK,
    TIMEZONE,
    TREKTELLEN_ERA,
    civil_twilight,
    parse_surveys,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/archive/mixed-weather-intervals"
OUT.mkdir(parents=True, exist_ok=True)
release = ROOT.parent / "defile-dataset/output/dataset"
surveys = parse_surveys(pd.read_csv(release / "survey.csv", low_memory=False))
counts = pd.read_csv(release / "count.csv", low_memory=False)
scope = pd.read_csv(ROOT / "scripts/research/weather_species.tsv", sep="\t")
taxa = pd.read_csv(release / "taxonomy.csv")
taxa = taxa[taxa.english_name.isin(scope.english_name)]
recent = surveys[
    surveys.date.dt.year.between(2022, 2025) & surveys.recording_era.eq(TREKTELLEN_ERA)
]
recent = recent[recent.survey_complete.eq(True) & ~recent.weather_stop.eq(True)]
timing = H.count_timing(counts, recent)
# Released outside-survey entries can have date-only timing; preserve that evidence.
outside = timing.remark_processing.fillna("").str.contains(OUTSIDE_SURVEY_REMARK, regex=False)
unknown = timing[
    timing.timing_status.eq("presence_only") | outside | timing.timing_status.eq("outside_survey")
]
unknown_keys = unknown[["survey_id", "taxon_id"]].drop_duplicates().assign(unknown=True)
frame = H.recording_scope(H.species_hours(H.survey_hours(recent), timing, taxa), scope)
frame = frame.merge(unknown_keys, on=["survey_id", "taxon_id"], how="left")
frame = frame[frame.unknown.ne(True) & frame.scope_available]
frame = frame[frame.start.dt.year.between(2022, 2025)]
complete = frame[frame.hourly_complete].copy()
complete["resolution"] = "hour"
coarse_keys = frame[~frame.hourly_complete][
    ["survey_id", "taxon_id", "english_name"]
].drop_duplicates()
coarse = coarse_keys.merge(recent[["survey_id", "start", "end", "date"]], on="survey_id")
totals = timing.groupby(["survey_id", "taxon_id"], as_index=False)["count"].sum()
coarse = coarse.merge(totals, on=["survey_id", "taxon_id"], validate="one_to_one")
coarse["exposure_hours"] = (coarse.end - coarse.start) / pd.Timedelta(hours=1)
coarse["resolution"] = "survey"
columns = [
    "survey_id",
    "taxon_id",
    "english_name",
    "date",
    "start",
    "end",
    "exposure_hours",
    "count",
    "resolution",
]
observations = pd.concat([complete[columns], coarse[columns]], ignore_index=True)
observations["observation_id"] = observations.index
assert not set(map(tuple, complete[["survey_id", "taxon_id"]].values)) & set(
    map(tuple, coarse_keys[["survey_id", "taxon_id"]].values)
)
# Retain actual bounds for weather integration; a survey total is never divided into counts.
parts = []
for row in observations.itertuples():
    for slot in pd.date_range(row.start.floor("h"), row.end.ceil("h"), freq="h", inclusive="left"):
        start, end = max(row.start, slot), min(row.end, slot + pd.Timedelta(hours=1))
        parts.append((row.observation_id, slot, start, end, (end - start) / pd.Timedelta(hours=1)))
components = pd.DataFrame(
    parts, columns=["observation_id", "slot_start", "start", "end", "fraction"]
)
np_hours = components.groupby("observation_id").fraction.sum().reindex(observations.observation_id)
assert abs(np_hours.to_numpy() - observations.exposure_hours.to_numpy()).max() < 1e-8
observations.to_csv(OUT / "observations.csv", index=False)
weather = pd.read_csv(ROOT / "data/archive/hourly-weather-priority/weather_hourly.csv")
weather["slot_start"] = pd.to_datetime(weather.slot_start, utc=True)
components = components.merge(weather, on="slot_start", how="left", validate="many_to_one")
components["date"] = (
    components.slot_start.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
)
dawn, dusk = civil_twilight(components.date)
components["tau"] = (components.slot_start + pd.Timedelta(minutes=30) - dawn) / (dusk - dawn)
components["year"] = components.date.dt.year
components["doy"] = components.date.dt.dayofyear - (
    components.date.dt.is_leap_year & components.date.dt.month.gt(2)
)
components["weather_available"] = (
    components[
        [
            "rain_mm",
            "rain_previous_24h_mm",
            "wind_u_m_s",
            "wind_v_m_s",
            "radiation_w_m2",
            "low_cloud_fraction",
        ]
    ]
    .notna()
    .all(axis=1)
)
components.to_csv(OUT / "hour_components.csv", index=False)

# Inventory recorded historical totals, including why they cannot yet enter training.
historical = surveys[surveys.date.dt.year.lt(2022)]
historical_counts = counts[counts.count_category.eq(MAIN_CATEGORY)].merge(
    taxa[["taxon_id", "english_name"]], on="taxon_id"
)
historical_counts = historical_counts.merge(
    historical[
        ["survey_id", "start", "end", "date", "survey_complete", "weather_stop", "recording_era"]
    ],
    on="survey_id",
)
historical_totals = historical_counts.groupby(
    ["survey_id", "taxon_id", "english_name", "start", "end", "date", "recording_era"],
    as_index=False,
).agg(
    recorded_count=("count", "sum"),
    presence_only=("count", lambda x: x.isna().any()),
    survey_complete=("survey_complete", "first"),
    weather_stop=("weather_stop", "first"),
)
historical_totals["recording_scope"] = "unverified historical species-survey coverage"
historical_totals["training_eligible"] = False
historical_totals.to_csv(OUT / "historical_recorded_totals.csv", index=False)
summary = observations.groupby(["english_name", "resolution"], as_index=False).agg(
    observations=("count", "size"), birds=("count", "sum"), hours=("exposure_hours", "sum")
)
summary.to_csv(OUT / "summary.csv", index=False)
(OUT / "metadata.json").write_text(
    json.dumps(
        {
            "recent_scope": "Complete 2022–2025 surveys; passerine zeros confirmed by user; priority 2022 coverage assumed",
            "historical_scope": "Recorded totals inventoried only; no historical absence converted to zero",
            "unknown_exclusions": "Presence-only or outside-survey entry excludes the entire species-survey",
            "likelihood": "Canonical-hour hurdle with binomial thinning; shared state requires joint likelihood for any intervals sharing a clock hour",
        },
        indent=2,
    )
    + "\n"
)
print(summary.to_string(index=False))
print(f"Historical recorded species-survey totals inventoried: {len(historical_totals)}")
