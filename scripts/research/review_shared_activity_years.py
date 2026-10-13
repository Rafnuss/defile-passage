"""Review the shared weather-activity model on leave-one-year-out folds."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs/shared-activity-year-review"
OUTPUT.mkdir(parents=True, exist_ok=True)

days = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/hourly-weather-{group}-year/held_out_days.csv")
        for group in ["priority", "passerines"]
    ],
    ignore_index=True,
)
hours = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/hourly-weather-{group}-year/held_out_hours.csv")
        for group in ["priority", "passerines"]
    ],
    ignore_index=True,
)
shared_days = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/shared-activity-{group}-year/shared_activity_held_out_days.csv")
        for group in ["priority", "passerines"]
    ],
    ignore_index=True,
)
shared_hours = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/shared-activity-{group}-year/shared_activity_held_out_hours.csv")
        for group in ["priority", "passerines"]
    ],
    ignore_index=True,
)
days = pd.concat([days, shared_days], ignore_index=True)
hours = pd.concat([hours, shared_hours], ignore_index=True)
keys = ["english_name", "date", "fold", "gap"]
rain = shared_hours[keys + ["rain_mm", "exposure_hours"]].copy()
rain["rain_exposure"] = rain.rain_mm * rain.exposure_hours
rain = rain.groupby(keys, as_index=False).agg(
    rain_exposure=("rain_exposure", "sum"), exposure_hours=("exposure_hours", "sum")
)
rain["rain_mm"] = rain.rain_exposure / rain.exposure_hours
days = days.drop(columns="rain_mm").merge(
    rain[keys + ["rain_mm"]], on=keys, validate="many_to_one"
)

assert set(days.loc[days.model.eq("shared_weather_activity"), "year"]) == {2022, 2023, 2024, 2025}
matching = days.groupby(["english_name", "date", "fold", "gap"]).agg(
    models=("model", "nunique"), truths=("count", "nunique")
)
assert (matching.models == 3).all() and (matching.truths == 1).all()
reconciled = (
    hours.groupby(["english_name", "model", "fold", "date"], as_index=False)
    .agg(count=("count", "sum"), predicted=("predicted", "sum"))
    .merge(shared_days, on=["english_name", "model", "fold", "date"], suffixes=("_hour", "_day"))
)
assert (reconciled.count_hour == reconciled.count_day).all()
assert np.allclose(reconciled.predicted_hour, reconciled.predicted_day, atol=1e-6)

for frame in [days, hours]:
    frame["weather_group"] = np.where(frame.rain_mm >= 0.1, "wet", "dry")
assert (days.groupby(keys).weather_group.nunique() == 1).all()

scores = days.groupby(
    ["year", "english_name", "model", "gap", "weather_group"], as_index=False
).agg(
    days=("count", "size"),
    mae=(
        "predicted",
        lambda prediction: np.mean(np.abs(prediction - days.loc[prediction.index, "count"])),
    ),
    actual=("count", "sum"),
    predicted=("predicted", "sum"),
)
reference = scores.loc[
    scores.model.eq("gamma_day_flocks"), ["year", "english_name", "gap", "weather_group", "mae"]
].rename(columns={"mae": "gamma_mae"})
scores = scores.merge(reference, on=["year", "english_name", "gap", "weather_group"])
scores["gamma_mae_ratio"] = scores.mae / scores.gamma_mae
scores["bias_fraction"] = scores.predicted / scores.actual - 1
scores.to_csv(OUTPUT / "species_scores.csv", index=False)
macro = scores.groupby(["year", "model", "gap", "weather_group"], as_index=False).agg(
    species=("english_name", "nunique"),
    mean_gamma_mae_ratio=("gamma_mae_ratio", "mean"),
    species_better_than_gamma=("gamma_mae_ratio", lambda ratio: int((ratio < 1).sum())),
    mean_absolute_bias=("bias_fraction", lambda bias: float(np.mean(np.abs(bias)))),
    actual_birds=("actual", "sum"),
    predicted_birds=("predicted", "sum"),
)
macro.to_csv(OUTPUT / "species_balanced_scores.csv", index=False)

hour_scores = hours.groupby(
    ["year", "english_name", "model", "weather_group"], as_index=False
).agg(
    hours=("count", "size"),
    mae=(
        "predicted",
        lambda prediction: np.mean(np.abs(prediction - hours.loc[prediction.index, "count"])),
    ),
)
hour_reference = hour_scores.loc[
    hour_scores.model.eq("gamma_day_flocks"), ["year", "english_name", "weather_group", "mae"]
].rename(columns={"mae": "gamma_mae"})
hour_scores = hour_scores.merge(hour_reference, on=["year", "english_name", "weather_group"])
hour_scores["gamma_mae_ratio"] = hour_scores.mae / hour_scores.gamma_mae
hour_scores.to_csv(OUTPUT / "hourly_species_scores.csv", index=False)
hour_macro = hour_scores.groupby(["year", "model", "weather_group"], as_index=False).agg(
    species=("english_name", "nunique"),
    mean_gamma_mae_ratio=("gamma_mae_ratio", "mean"),
    species_better_than_gamma=("gamma_mae_ratio", lambda ratio: int((ratio < 1).sum())),
)
hour_macro.to_csv(OUTPUT / "hourly_species_balanced_scores.csv", index=False)

hours["observed_active"] = hours["count"] > 0
hours["rain_band"] = pd.cut(
    hours.rain_mm,
    [-np.inf, 0.1, 1, 3, np.inf],
    labels=["<0.1", "0.1-1", "1-3", ">=3"],
    right=False,
)
activity = hours.loc[hours.model.eq("shared_weather_activity")].copy()
activity["brier"] = (activity.active_probability - activity.observed_active.astype(float)) ** 2
calibration = activity.groupby(["year", "rain_band"], observed=True, as_index=False).agg(
    held_out_hours=("count", "size"),
    observed_active_fraction=("observed_active", "mean"),
    predicted_active_fraction=("active_probability", "mean"),
    brier_score=("brier", "mean"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
)
calibration.to_csv(OUTPUT / "activity_calibration.csv", index=False)

print("Leave-one-year-out species-balanced MAE ratios versus matched Gamma-day model")
print(macro.to_string(index=False))
print("\nHourly species-balanced MAE ratios versus matched Gamma-day model")
print(hour_macro.to_string(index=False))
print("\nHeld-out occurrence and count calibration by year and rain band")
print(calibration.to_string(index=False))
print("\nAnnual truth matching and hourly-to-daily reconciliation passed")
