"""Assemble actual historical count/effort observations; scope stays explicit.

Run with uv run --with 'pyarrow<20' python scripts/research/prepare_historical_counts.py. Absent
entries remain unknown outside the adopted taxonomy start and annual-record panel.
"""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

from defile_explore.export import in_window
from defile_explore.release import (
    MAIN_CATEGORY,
    OUTSIDE_SURVEY_REMARK,
    TIMEZONE,
    civil_twilight,
    parse_surveys,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/historical-counts"
OUT.mkdir(exist_ok=True)
RELEASE = ROOT.parent / "defile-dataset/output/dataset"
CACHE = ROOT.parent / "defile-migration-forecast/data/weather/era5_hourly/location=Defile"

# Recorded counts and actual support, without assumed weather-stop zeros.
scope = pd.read_csv(ROOT / "scripts/research/historical_core_scope.tsv", sep="\t")
taxa = pd.read_csv(RELEASE / "taxonomy.csv")
taxa = taxa[taxa.english_name.isin(scope.english_name)][
    ["taxon_id", "english_name", "systematic_count_start_year"]
].copy()
surveys = parse_surveys(pd.read_csv(RELEASE / "survey.csv", low_memory=False))
counts = pd.read_csv(RELEASE / "count.csv", low_memory=False)
annual = counts[counts.count_category.eq(MAIN_CATEGORY) & counts["count"].gt(0)].merge(
    surveys[["survey_id", "date"]], on="survey_id"
)
annual["year"] = annual.date.dt.year
coverage = []
for taxon in (
    pd.read_csv(RELEASE / "taxonomy.csv")
    .dropna(subset=["systematic_count_start_year"])
    .itertuples()
):
    start = int(taxon.systematic_count_start_year)
    present = set(annual.loc[annual.taxon_id.eq(taxon.taxon_id), "year"])
    missing = sorted(set(range(start, 2026)) - present)
    coverage.append((taxon.english_name, start, ",".join(map(str, missing)), not missing))
coverage = pd.DataFrame(
    coverage, columns=["english_name", "scope_from", "missing_years_to_2025", "confirmed"]
)
coverage.to_csv(OUT / "taxonomy_annual_coverage.csv", index=False)
taxa = taxa.merge(coverage, on="english_name", how="left")
taxa["scope_to"] = 2021
taxa["confirmed"] = taxa.confirmed.eq(True)
taxa[
    "evidence"
] = "Adopted taxonomy start; positive main-direction record in every year through 2025"
taxa.to_csv(OUT / "core_species_scope.csv", index=False)
surveys = surveys[surveys.date.dt.year.between(1993, 2021) & in_window(surveys.date)].copy()
counts = (
    counts[counts.count_category.eq(MAIN_CATEGORY)]
    .merge(taxa[["taxon_id", "english_name"]], on="taxon_id")
    .merge(surveys[["survey_id", "start", "end", "date"]], on="survey_id")
)
raw = counts.datetime.fillna("")
point = raw.str.contains("T") & ~raw.str.contains("/")
time = pd.to_datetime(raw.where(point), format="ISO8601", utc=True)
bounds = raw.where(raw.str.contains("/")).str.split("/", expand=True).reindex(columns=[0, 1])
a, b = pd.to_datetime(bounds[0], format="ISO8601", utc=True), pd.to_datetime(
    bounds[1], format="ISO8601", utc=True
)
counts["unsupported_support"] = (
    (point & (time.lt(counts.start) | time.ge(counts.end)))
    | a.lt(counts.start)
    | b.gt(counts.end)
    | counts.remark_processing.fillna("").str.contains(OUTSIDE_SURVEY_REMARK, regex=False)
)
counts["presence_only"] = counts["count"].isna()
issues = counts[counts.unsupported_support | counts.presence_only].copy()
issues.to_csv(OUT / "count_support_issues.csv", index=False)
# A broad count may span other sessions on its date: exclude the whole species-date.
unknown = issues[["taxon_id", "date"]].drop_duplicates().assign(unknown_support=True)
recorded = counts.groupby(["survey_id", "taxon_id"], as_index=False).agg(
    recorded_count=("count", lambda x: x.sum(min_count=1)), entries=("count_id", "size")
)
observed = surveys[surveys.survey_complete.eq(True) & ~surveys.weather_stop.eq(True)].copy()
observations = (
    observed.merge(taxa, how="cross")
    .merge(recorded, on=["survey_id", "taxon_id"], how="left")
    .merge(unknown, on=["taxon_id", "date"], how="left")
)
observations["year"] = observations.date.dt.year
observations["scope_verified"] = observations.confirmed & observations.year.between(
    observations.scope_from, observations.scope_to
)
observations["count"] = observations.recorded_count
observations.loc[observations.scope_verified & observations.recorded_count.isna(), "count"] = 0
observations["exposure_hours"] = (observations.end - observations.start).dt.total_seconds() / 3600
observations["resolution"] = "survey"
observations["observation_id"] = np.arange(len(observations))
observations["training_eligible"] = observations.scope_verified & ~observations.unknown_support.eq(
    True
)

# Integrate hourly predictors across exposure; never distribute an observed survey count.
parts = []
for row in observed.itertuples():
    edges = [row.start, *pd.date_range(row.start.ceil("h"), row.end, freq="h"), row.end]
    for start, end in zip(edges[:-1], edges[1:]):
        if end > start:
            parts.append(
                (
                    row.survey_id,
                    start.floor("h"),
                    start,
                    end,
                    (end - start) / pd.Timedelta(hours=1),
                )
            )
hours = pd.DataFrame(parts, columns=["survey_id", "slot_start", "start", "end", "fraction"])
weather = pd.concat(
    [
        pd.read_parquet(
            part,
            columns=[
                "datetime",
                "total_precipitation",
                "u_component_of_wind_10m",
                "v_component_of_wind_10m",
            ],
        )
        for part in sorted(CACHE.glob("part-*.parquet"))
    ],
    ignore_index=True,
).sort_values("datetime")
weather["slot_start"] = pd.to_datetime(weather.datetime, utc=True)
assert weather.slot_start.diff().dropna().eq(pd.Timedelta(hours=1)).all()
weather["rain_mm"] = weather.total_precipitation.shift(-1) * 1000
weather["wind_u_m_s"] = (
    weather.u_component_of_wind_10m + weather.u_component_of_wind_10m.shift(-1)
) / 2
weather["wind_v_m_s"] = (
    weather.v_component_of_wind_10m + weather.v_component_of_wind_10m.shift(-1)
) / 2
hours = hours.merge(
    weather[["slot_start", "rain_mm", "wind_u_m_s", "wind_v_m_s"]],
    on="slot_start",
    how="left",
    validate="many_to_one",
)
hours["date"] = hours.start.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
dawn, dusk = civil_twilight(hours.date)
hours["tau"] = (hours.slot_start + pd.Timedelta(minutes=30) - dawn) / (dusk - dawn)
hours["year"] = hours.date.dt.year
hours["doy"] = hours.date.dt.dayofyear - (hours.date.dt.is_leap_year & hours.date.dt.month.gt(2))
components = observations[
    ["observation_id", "survey_id", "english_name", "training_eligible"]
].merge(hours, on="survey_id")
assert components[["rain_mm", "wind_u_m_s", "wind_v_m_s", "tau"]].notna().all().all()
exposure = components.groupby("observation_id").fraction.sum().reindex(observations.observation_id)
assert np.allclose(exposure, observations.exposure_hours)
assert not observations.duplicated(["survey_id", "taxon_id"]).any()
observations.to_csv(OUT / "observations.csv", index=False)
components.to_csv(OUT / "components.csv", index=False)
observations["absent_entry"] = observations.entries.isna()
summary = observations.groupby(["year", "english_name"], as_index=False).agg(
    observations=("observation_id", "size"),
    recorded_observations=("entries", "count"),
    absent_entries=("absent_entry", "sum"),
    recorded_birds=("recorded_count", "sum"),
    hours=("exposure_hours", "sum"),
    eligible=("training_eligible", "sum"),
    unknown_support=("unknown_support", lambda x: x.eq(True).sum()),
)
summary.to_csv(OUT / "year_species_inventory.csv", index=False)
sources = [
    RELEASE / "survey.csv",
    RELEASE / "count.csv",
    RELEASE / "taxonomy.csv",
    ROOT / "scripts/research/historical_core_scope.tsv",
]
sources += sorted(CACHE.glob("part-*.parquet"))
(OUT / "metadata.json").write_text(
    json.dumps(
        dict(
            source_hashes={str(p): sha256(p.read_bytes()).hexdigest() for p in sources},
            scope="Absent entries unknown outside adopted taxonomy start and annually recorded core panel; weather stops excluded",
            support="Any unresolved count support excludes the complete species-date",
            units="Elapsed hours; rain at t+1 describes [t,t+1); mean wind endpoints",
            observed_surveys=len(observed),
            support_issues=len(issues),
            unknown_species_dates=len(unknown),
        ),
        indent=2,
    )
    + "\n"
)
print(
    summary.groupby("english_name")[
        ["observations", "absent_entries", "recorded_birds", "eligible", "unknown_support"]
    ]
    .sum()
    .to_string()
)
print(
    "Historical components:",
    len(components),
    "; support issues:",
    len(issues),
    "; unknown species-dates:",
    len(unknown),
)
