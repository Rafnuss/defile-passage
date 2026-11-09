"""Audit candidate species before expanding the hourly weather experiment.

Selection uses observed data characteristics, never held-out model performance.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage import hourly as H
from defile_passage.catalogue import group_of
from defile_passage.export import start_year
from defile_passage.release import MAIN_CATEGORY, TREKTELLEN_ERA, civil_twilight, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT.parent / "defile-dataset/output/dataset"
OUTPUT = ROOT / "logs/hourly-weather-species"
YEARS = (2022, 2023, 2024, 2025)
MIN_POSITIVE_DAYS = 40
MIN_BIRDS = 500
MIN_COMPLETE_SHARE = 0.8
MIN_WET_POSITIVE_DAYS = 20
OUTPUT.mkdir(parents=True, exist_ok=True)
surveys = parse_surveys(pd.read_csv(DATASET / "survey.csv", low_memory=False))
surveys = surveys[surveys.recording_era.eq(TREKTELLEN_ERA) & surveys.date.dt.year.isin(YEARS)]
all_counts = pd.read_csv(DATASET / "count.csv", low_memory=False)
timing = H.count_timing(all_counts, surveys)
taxonomy = pd.read_csv(DATASET / "taxonomy.csv")
taxa = taxonomy[taxonomy.taxon_rank.eq("species") & taxonomy.taxon_id.isin(timing.taxon_id)]
hours = H.survey_hours(surveys)
frame = H.species_hours(hours, timing, taxa)
dawn, dusk = civil_twilight(pd.to_datetime(frame.date))
frame = frame[frame.start.ge(dawn) & frame.end.le(dusk)].copy()
weather = pd.read_csv(ROOT / "archive/hourly-weather/weather_hourly.csv")
weather["slot_start"] = pd.to_datetime(weather.slot_start, utc=True)
frame = frame.merge(weather[["slot_start", "rain_mm"]], on="slot_start", validate="many_to_one")
frame["year"] = pd.to_datetime(frame.date).dt.year
dates = pd.to_datetime(frame.date)
frame["doy"] = dates.dt.dayofyear - (dates.dt.is_leap_year & dates.dt.month.gt(2))
eligible = frame[frame.hourly_complete & frame.rain_mm.notna()]
summary = []
for taxon in taxa.itertuples():
    rows = eligible[eligible.taxon_id.eq(taxon.taxon_id)]
    daily = rows.groupby("date")["count"].sum()
    positive = rows[rows["count"].gt(0)]
    yearly = positive.groupby("year")["count"].sum().reindex(YEARS, fill_value=0)
    ordered = positive.sort_values("doy")
    cumulative = ordered["count"].cumsum() / ordered["count"].sum()
    quantiles = (
        np.interp([0.1, 0.5, 0.9], cumulative, ordered.doy) if len(ordered) else [np.nan] * 3
    )
    hourly = rows.groupby(["date", "slot_start"])["count"].sum()
    wet = rows.rain_mm.ge(0.1)
    summary.append(
        dict(
            taxon_id=taxon.taxon_id,
            english_name=taxon.english_name,
            group="pigeons"
            if taxon.order == "Columbiformes"
            else group_of(taxon.order, taxon.scientific_name),
            family=taxon.family,
            eligible_hours=rows.exposure_hours.sum(),
            complete_share=rows.exposure_hours.sum()
            / frame.loc[frame.taxon_id.eq(taxon.taxon_id), "exposure_hours"].sum(),
            birds=rows["count"].sum(),
            positive_days=daily.gt(0).sum(),
            positive_years=yearly.gt(0).sum(),
            zero_fraction_if_recorded=hourly.eq(0).mean(),
            peak_hour_share=hourly.max() / hourly.sum() if hourly.sum() > 0 else np.nan,
            peak_day_share=daily.max() / daily.sum() if daily.sum() > 0 else np.nan,
            passage_q10=quantiles[0],
            passage_q50=quantiles[1],
            passage_q90=quantiles[2],
            wet_hours=rows.loc[wet, "exposure_hours"].sum(),
            wet_positive_days=rows[wet & rows["count"].gt(0)].date.nunique(),
            wet_birds=rows.loc[wet, "count"].sum(),
        )
    )
summary = pd.DataFrame(summary).sort_values("birds", ascending=False)
summary["core_eligible"] = (
    summary.birds.ge(MIN_BIRDS)
    & summary.positive_days.ge(MIN_POSITIVE_DAYS)
    & summary.positive_years.eq(len(YEARS))
    & summary.complete_share.ge(MIN_COMPLETE_SHARE)
    & summary.wet_positive_days.ge(MIN_WET_POSITIVE_DAYS)
)
summary.to_csv(OUTPUT / "candidate_audit.csv", index=False)
print(summary.head(45).round(3).to_string(index=False))

selection = pd.read_csv(ROOT / "scripts/research/weather_species.tsv", sep="\t").merge(
    summary, on="english_name", validate="one_to_one"
)
assert selection.loc[selection.role.eq("main"), "core_eligible"].all()
print(
    selection[
        [
            "english_name",
            "role",
            "birds",
            "positive_days",
            "wet_positive_days",
            "zero_fraction_if_recorded",
            "passage_q50",
        ]
    ]
    .round(3)
    .to_string(index=False)
)

# A historical start-year rule is descriptive; it never verifies recording scope.
count_years = all_counts[all_counts.count_category.eq(MAIN_CATEGORY)].merge(
    parse_surveys(pd.read_csv(DATASET / "survey.csv", low_memory=False))[["survey_id", "date"]],
    on="survey_id",
    validate="many_to_one",
)
annual = (
    count_years.assign(year=count_years.date.dt.year).groupby(["taxon_id", "year"])["count"].sum()
)
selection = selection.merge(taxonomy[["taxon_id", "order"]], on="taxon_id", validate="one_to_one")
selection["existing_start_year_rule"] = [
    start_year(r.order, r.family, annual.loc[r.taxon_id].to_dict(), max(YEARS))
    for r in selection.itertuples()
]
selection["fit_eligible"] = selection.core_eligible & selection.recording_scope.isin(
    H.COUNTED_SCOPES
)
selection["analysis_years"] = ",".join(map(str, YEARS))
selection["scope_evidence"] = np.where(
    selection.recording_scope.eq("priority_target"),
    "2023-2025 report monitoring/methods; 2022 continuity assumed, full report unavailable",
    "User confirmation on 2026-10-10: all passerines counted throughout complete surveys in 2022-2025; earlier scope unverified",
)
selection.to_csv(OUTPUT / "selected_species.csv", index=False)
