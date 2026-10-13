"""Assess simple-rate annual predictions on matching observed intervals."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--candidate", default="rain_daylight")
args = parser.parse_args()
candidate = args.candidate
out = root / f"logs/simple-panel-review-{candidate}"
out.mkdir(exist_ok=True)
predictions, diagnostics, status, tags = [], [], [], []
for panel in ["priority", "passerines"]:
    folder = root / f"logs/simple-panel-{panel}"
    predictions.append(pd.read_csv(folder / "predictions.csv").query("variant == 'baseline'"))
    diagnostics.append(pd.read_csv(folder / "diagnostics.csv").query("variant == 'baseline'"))
    status.append(pd.read_csv(folder / "status.csv").query("variant == 'baseline'"))
    candidate_folder = root / f"logs/simple-{candidate}-panel-{panel}"
    if candidate == "rain_daylight":
        candidate_folder = folder
    predictions.append(
        pd.read_csv(candidate_folder / "predictions.csv").query("variant == @candidate")
    )
    diagnostics.append(
        pd.read_csv(candidate_folder / "diagnostics.csv").query("variant == @candidate")
    )
    status.append(pd.read_csv(candidate_folder / "status.csv").query("variant == @candidate"))
    inputs = root / f"logs/simple-rate-all-design-{panel}"
    for context in pd.read_csv(inputs / "manifest.csv").itertuples():
        components = pd.read_csv(inputs / f"{context.key}_components.csv")
        components["rain_exposure"] = components.rain_mm * components.fraction
        frame = (
            components.groupby("observation_id")
            .agg(
                tau_min=("tau", "min"),
                tau_max=("tau", "max"),
                rain_exposure=("rain_exposure", "sum"),
                hours=("fraction", "sum"),
            )
            .reset_index()
        )
        frame["english_name"], frame["fold"] = context.english_name, context.fold
        tags.append(frame)
predictions = pd.concat(predictions, ignore_index=True).merge(
    pd.concat(tags), on=["english_name", "fold", "observation_id"], validate="many_to_one"
)
diagnostics, status = pd.concat(diagnostics), pd.concat(status)
assert not predictions.duplicated(["variant", "english_name", "observation_id"]).any()
predictions["rain"] = predictions.rain_exposure / predictions.hours
predictions["wet"] = predictions.rain >= 0.1
predictions["outside_daylight"] = (predictions.tau_min < 0) | (predictions.tau_max > 1)
predictions["absolute_error"] = (predictions["count"] - predictions.predicted).abs()
scores = (
    predictions.groupby(["variant", "english_name", "fold", "resolution", "wet"])
    .agg(
        observations=("count", "size"),
        observed=("count", "sum"),
        predicted=("predicted", "sum"),
        mae=("absolute_error", "mean"),
    )
    .reset_index()
)
scores.to_csv(out / "species_scores.csv", index=False)
special = []
for label, mask in [
    ("outside_daylight_hour", predictions.resolution.eq("hour") & predictions.outside_daylight),
    ("heavy_rain_hour", predictions.resolution.eq("hour") & (predictions.rain >= 3)),
    ("intact_survey", predictions.resolution.ne("hour")),
]:
    frame = (
        predictions[mask]
        .groupby(["variant", "english_name", "fold"])
        .agg(
            observations=("count", "size"),
            observed=("count", "sum"),
            predicted=("predicted", "sum"),
            mae=("absolute_error", "mean"),
        )
        .reset_index()
    )
    frame["group"] = label
    special.append(frame)
pd.concat(special).to_csv(out / "special_scores.csv", index=False)

# Match both candidates before aggregating days and resampling shared weeks.
paired = (
    predictions.pivot(
        index=["english_name", "fold", "observation_id"], columns="variant", values="predicted"
    )
    .dropna()
    .reset_index()
)
truth = predictions[predictions.variant.eq("baseline")].drop(columns=["predicted", "variant"])
paired = paired.merge(truth, on=["english_name", "fold", "observation_id"], validate="one_to_one")
matched_special = []
for label, mask in [
    ("outside_daylight_hour", paired.resolution.eq("hour") & paired.outside_daylight),
    ("heavy_rain_hour", paired.resolution.eq("hour") & (paired.rain >= 3)),
    ("intact_survey", paired.resolution.ne("hour")),
]:
    frame = paired[mask]
    matched_special.append(
        dict(
            group=label,
            observations=len(frame),
            observed=frame["count"].sum(),
            baseline=frame.baseline.sum(),
            candidate=frame[candidate].sum(),
        )
    )
pd.DataFrame(matched_special).to_csv(out / "matched_special_scores.csv", index=False)
daily = (
    paired.groupby(["english_name", "fold", "date"])
    .agg(
        observed=("count", "sum"),
        baseline=("baseline", "sum"),
        candidate=(candidate, "sum"),
        hours=("hours", "sum"),
        rain_exposure=("rain_exposure", "sum"),
    )
    .reset_index()
)
daily["wet"] = daily.rain_exposure / daily.hours >= 0.1
daily["difference"] = (daily.candidate - daily.observed).abs() - (
    daily.baseline - daily.observed
).abs()
daily["week"] = (pd.to_datetime(daily.date) - pd.Timestamp("1970-01-05", tz="UTC")).dt.days // 7
daily.to_csv(out / "paired_daily.csv", index=False)
rng = np.random.default_rng(20261012)
weeks = np.sort(daily.week.unique())
weights = rng.multinomial(len(weeks), np.full(len(weeks), 1 / len(weeks)), size=800)
summary = []
for wet, frame in daily.groupby("wet"):
    totals = (
        frame.pivot_table(
            index="english_name", columns="week", values="difference", aggfunc="sum", fill_value=0
        )
        .reindex(columns=weeks, fill_value=0)
        .to_numpy()
    )
    counts = (
        frame.pivot_table(
            index="english_name", columns="week", values="difference", aggfunc="size", fill_value=0
        )
        .reindex(columns=weeks, fill_value=0)
        .to_numpy()
    )
    draws = ((totals @ weights.T) / (counts @ weights.T)).mean(axis=0)
    summary.append(
        dict(
            wet=wet,
            species=len(totals),
            days=len(frame),
            difference=frame.groupby("english_name").difference.mean().mean(),
            low=np.quantile(draws, 0.025),
            high=np.quantile(draws, 0.975),
        )
    )
pd.DataFrame(summary).to_csv(out / "paired_week_bootstrap.csv", index=False)
diagnostics.to_csv(out / "fit_diagnostics.csv", index=False)
status.to_csv(out / "status.csv", index=False)
print(status.groupby("variant").passed.agg(["sum", "count"]).to_string())
print(pd.DataFrame(summary).to_string(index=False))
