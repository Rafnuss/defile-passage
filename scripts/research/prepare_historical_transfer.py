"""Freeze historical attendance templates and a separate weather-based transfer mask."""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage.export import in_window
from defile_passage.release import TIMEZONE, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/historical-transfer"
OUT.mkdir(exist_ok=True)
annual = pd.read_csv(ROOT / "logs/gap-target-audit/year.csv")
templates = []
for era, first, last in [
    ("early", 1993, 2007),
    ("staff", 2008, 2016),
    ("live", 2017, 2021),
    ("pre1993", 1966, 1992),
]:
    group = annual[annual.year.between(first, last)].copy()
    group["distance"] = abs(
        group.daylight_effort_fraction - group.daylight_effort_fraction.median()
    )
    chosen = group.sort_values(["distance", "year"]).iloc[0]
    templates.append(
        dict(
            scenario=era,
            template_year=int(chosen.year),
            historical_coverage=chosen.daylight_effort_fraction,
        )
    )
pd.DataFrame(templates).to_csv(OUT / "templates.csv", index=False)
surveys = parse_surveys(
    pd.read_csv(ROOT.parent / "defile-dataset/output/dataset/survey.csv", low_memory=False)
)
surveys = surveys[
    surveys.survey_complete.eq(True) & ~surveys.weather_stop.eq(True) & in_window(surveys.date)
].copy()
surveys["month_day"] = surveys.date.dt.strftime("%m-%d")
for name in ["start", "end"]:
    local = surveys[name].dt.tz_convert(TIMEZONE)
    surveys[name + "_hour"] = (local - local.dt.normalize()).dt.total_seconds() / 3600

# An observed interval is indivisible; retain it only if wholly covered by the template.
manifest, audits = [], []
for panel in ["priority", "passerines"]:
    rows = pd.read_csv(ROOT / f"archive/hourly-weather-{panel}/validation_masks.csv")
    rows = rows[in_window(pd.to_datetime(rows.date))].copy()
    for name in ["start", "end"]:
        local = pd.to_datetime(rows[name], utc=True).dt.tz_convert(TIMEZONE)
        rows[name + "_hour"] = (local - local.dt.normalize()).dt.total_seconds() / 3600
    rows["month_day"] = pd.to_datetime(rows.date).dt.strftime("%m-%d")
    for scenario in templates + [dict(scenario="weather", template_year=0)]:
        keep = pd.Series(False, index=rows.index)
        if scenario["scenario"] == "weather":
            # Rain selection is independent of counts; dry logistical gaps rotate through the season.
            keep = rows.rain_mm.lt(0.1) & ~((rows.doy % 21).between(5, 7))
        else:
            historical = surveys[surveys.date.dt.year.eq(scenario["template_year"])]
            for day, sessions in historical.groupby("month_day"):
                selected = rows.month_day.eq(day)
                covered = np.zeros(selected.sum(), dtype=bool)
                for session in sessions.itertuples():
                    covered |= (
                        rows.loc[selected, "start_hour"].ge(session.start_hour)
                        & rows.loc[selected, "end_hour"].le(session.end_hour)
                    ).to_numpy()
                keep.loc[selected] = covered
        for target_year in range(2022, 2026):
            for species, sample in rows.groupby("english_name"):
                sample = sample.copy()
                sample["hidden"] = sample.year.eq(target_year) & ~keep.loc[sample.index]
                sample["template_keep"] = keep.loc[sample.index]
                sample["target_year"] = target_year
                sample = sample.reset_index(drop=True)
                sample["fraction"] = sample.exposure_hours
                sample["row_id"] = np.arange(len(sample))
                for resolution in ["hour", "survey"]:
                    key = f"{species.replace(' ', '_')}_{scenario['scenario']}_{target_year}_{resolution}"
                    folder = OUT / "input"
                    folder.mkdir(exist_ok=True)
                    components = sample.copy()
                    # Coarsen only retained target-year connected runs, not their hidden count truth.
                    coarse = (
                        ~components.hidden
                        & components.year.eq(target_year)
                        & (resolution == "survey")
                    )
                    run = (
                        components.date.ne(components.date.shift())
                        | components.start.ne(components.end.shift())
                        | coarse.ne(coarse.shift())
                    )
                    components["observation_id"] = np.where(
                        coarse, run.cumsum() + len(components), components.row_id
                    )
                    observations = components.groupby(
                        "observation_id", sort=False, as_index=False
                    ).agg(
                        date=("date", "first"),
                        start=("start", "first"),
                        end=("end", "last"),
                        count=("count", "sum"),
                        exposure_hours=("exposure_hours", "sum"),
                        hidden=("hidden", "first"),
                    )
                    observations["resolution"] = np.where(
                        observations.observation_id.ge(len(components)), "survey", "hour"
                    )
                    observations["english_name"] = species
                    assert components.groupby("observation_id").hidden.nunique().eq(1).all()
                    assert observations["count"].sum() == components["count"].sum()
                    assert (
                        components.groupby("year")
                        .apply(lambda x: (~x.hidden).any(), include_groups=False)
                        .all()
                    )
                    components.to_csv(folder / f"{key}_components.csv", index=False)
                    observations.to_csv(folder / f"{key}_observations.csv", index=False)
                    manifest.append(
                        dict(
                            key=key,
                            english_name=species,
                            panel=panel,
                            scenario=scenario["scenario"],
                            template_year=scenario["template_year"],
                            target_year=target_year,
                            resolution=resolution,
                            fold=target_year - 2022,
                            heldout_year=np.nan,
                        )
                    )
                target = sample[sample.year.eq(target_year)]
                audits.append(
                    dict(
                        english_name=species,
                        panel=panel,
                        scenario=scenario["scenario"],
                        target_year=target_year,
                        observed_truth_hours=target.exposure_hours.sum(),
                        retained_hours=target.loc[~target.hidden, "exposure_hours"].sum(),
                        hidden_hours=target.loc[target.hidden, "exposure_hours"].sum(),
                        truth_dates=target.date.nunique(),
                        retained_dates=target.loc[~target.hidden, "date"].nunique(),
                    )
                )
pd.DataFrame(manifest).to_csv(OUT / "input/manifest.csv", index=False)
pd.DataFrame(audits).to_csv(OUT / "coverage.csv", index=False)
print(pd.DataFrame(templates).to_string(index=False))
print(f"Prepared {len(manifest)} contexts; target-year counts masked jointly by site attendance.")
