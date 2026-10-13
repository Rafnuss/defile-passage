"""Assess positive-count calibration before adding shared-day complexity."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs/weather-activity-positive-review"
OUTPUT.mkdir(parents=True, exist_ok=True)
frames = []
for variant, prefix in [
    ("simple_positive", "weather-activity-simple"),
    ("original", "weather-activity"),
    ("positive_penalty_10", "weather-activity-positive10"),
]:
    for group in ["priority", "passerines"]:
        frame = pd.read_csv(ROOT / f"logs/{prefix}-{group}/activity_held_out_hours.csv")
        frames.append(frame.assign(variant=variant))
hours = pd.concat(frames, ignore_index=True)
keys = ["english_name", "date", "start", "end", "fold", "gap"]
matching = hours.groupby(keys).agg(
    variants=("variant", "nunique"),
    truths=("count", "nunique"),
    gate=("active_probability", "nunique"),
)
assert (
    (matching.variants == 3).all() and (matching.truths == 1).all() and (matching.gate == 1).all()
)
hours["rain_band"] = pd.cut(
    hours.rain_mm,
    [-np.inf, 0.1, 1, 3, np.inf],
    labels=["<0.1", "0.1-1", "1-3", ">=3"],
    right=False,
)
hours["observed_positive"] = hours["count"] > 0
hours["positive_mean"] = hours.predicted / hours.active_probability
hours["observed_positive_count"] = hours["count"].where(hours.observed_positive)
hours["predicted_positive_count"] = hours.positive_mean.where(hours.observed_positive)
hours["positive_absolute_error"] = (
    (hours.positive_mean - hours["count"]).abs().where(hours.observed_positive)
)

# Folds 0–2 evaluate each observed interval once; fold 3 is a separate short-gap task.
species = hours.groupby(
    ["variant", "english_name", "gap", "rain_band"], observed=True, as_index=False
).agg(
    held_out_hours=("count", "size"),
    positive_hours=("observed_positive", "sum"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
    observed_positive_mean=("observed_positive_count", "mean"),
    predicted_positive_mean=("predicted_positive_count", "mean"),
    positive_mae=("positive_absolute_error", "mean"),
)
species["positive_mean_ratio"] = species.predicted_positive_mean / species.observed_positive_mean
species.to_csv(OUTPUT / "species_positive_calibration.csv", index=False)
by_year = hours.groupby(
    ["variant", "english_name", "year", "gap", "rain_band"], observed=True, as_index=False
).agg(
    held_out_hours=("count", "size"),
    positive_hours=("observed_positive", "sum"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
    positive_mae=("positive_absolute_error", "mean"),
)
by_year.to_csv(OUTPUT / "species_year_positive_calibration.csv", index=False)

hours["rain_exposure"] = hours.rain_mm * hours.exposure_hours
days = hours.groupby(
    ["variant", "english_name", "date", "year", "fold", "gap"], as_index=False
).agg(
    count=("count", "sum"),
    predicted=("predicted", "sum"),
    rain_exposure=("rain_exposure", "sum"),
    exposure=("exposure_hours", "sum"),
)
days["weather_group"] = np.where(days.rain_exposure / days.exposure >= 0.1, "wet", "dry")
days["absolute_error"] = (days.predicted - days["count"]).abs()
scores = days.groupby(["variant", "english_name", "gap", "weather_group"], as_index=False).agg(
    mae=("absolute_error", "mean")
)
reference = (
    scores.loc[scores.variant.eq("original")]
    .drop(columns="variant")
    .rename(columns={"mae": "original_mae"})
)
scores = scores.merge(reference, on=["english_name", "gap", "weather_group"])
scores["mae_ratio"] = scores.mae / scores.original_mae
scores.to_csv(OUTPUT / "species_gap_scores.csv", index=False)
summary = scores.groupby(["variant", "gap", "weather_group"], as_index=False).agg(
    mean_mae_ratio=("mae_ratio", "mean"),
    species_improved=("mae_ratio", lambda x: int((x < 1).sum())),
)
summary.to_csv(OUTPUT / "species_balanced_gap_scores.csv", index=False)
rain = hours.groupby(["variant", "gap", "rain_band"], observed=True, as_index=False).agg(
    held_out_hours=("count", "size"),
    positive_hours=("observed_positive", "sum"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
    observed_positive_mean=("observed_positive_count", "mean"),
    predicted_positive_mean=("predicted_positive_count", "mean"),
    positive_mae=("positive_absolute_error", "mean"),
)
rain.to_csv(OUTPUT / "rain_calibration.csv", index=False)
print(summary.to_string(index=False))
print("\nPositive-count and total-count calibration, with occurrence unchanged")
print(rain.to_string(index=False))
print("\nSpecies-specific heavy-rain support and calibration (each observed hour evaluated once)")
print(species.loc[species.gap.eq("days") & species.rain_band.eq(">=3")].to_string(index=False))
print("\nPaired observations, truths and unchanged occurrence gate verified")
