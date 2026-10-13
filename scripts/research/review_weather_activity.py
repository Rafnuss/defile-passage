"""Compare the two-part weather activity fit with matched daily-rate predictions."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs/hourly-weather-activity-review"
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "logs/hourly-weather-panel-v4"
groups = ["priority", "passerines"]
activity_days = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/weather-activity-{group}/activity_held_out_days.csv")
        for group in groups
    ],
    ignore_index=True,
)
activity_hours = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/weather-activity-{group}/activity_held_out_hours.csv")
        for group in groups
    ],
    ignore_index=True,
)
activity_diagnostics = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/weather-activity-{group}/activity_fit_diagnostics.csv")
        for group in groups
    ],
    ignore_index=True,
)
shared_days = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/shared-activity-{group}/shared_activity_held_out_days.csv")
        for group in groups
    ],
    ignore_index=True,
)
shared_hours = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/shared-activity-{group}/shared_activity_held_out_hours.csv")
        for group in groups
    ],
    ignore_index=True,
)
shared_diagnostics = pd.concat(
    [
        pd.read_csv(ROOT / f"logs/shared-activity-{group}/shared_activity_fit_diagnostics.csv")
        for group in groups
    ],
    ignore_index=True,
)
activity_days = pd.concat([activity_days, shared_days], ignore_index=True)
activity_hours = pd.concat([activity_hours, shared_hours], ignore_index=True)
days = pd.concat([pd.read_csv(BASE / "held_out_days.csv"), activity_days], ignore_index=True)
hours = pd.concat([pd.read_csv(BASE / "held_out_hours.csv"), activity_hours], ignore_index=True)
keys = ["english_name", "date", "fold", "gap"]
rain = hours.loc[hours.model.eq("weather_activity"), keys + ["rain_mm", "exposure_hours"]].copy()
rain["rain_exposure"] = rain.rain_mm * rain.exposure_hours
rain = rain.groupby(keys, as_index=False).agg(
    rain_exposure=("rain_exposure", "sum"), exposure_hours=("exposure_hours", "sum")
)
rain["rain_mm"] = rain.rain_exposure / rain.exposure_hours
days = days.drop(columns="rain_mm").merge(
    rain[keys + ["rain_mm"]], on=keys, validate="many_to_one"
)
days["weather_group"] = np.where(days.rain_mm >= 0.1, "wet", "dry")
hours["weather_group"] = np.where(hours.rain_mm >= 0.1, "wet", "dry")
days["block"] = (
    days.year.astype(str) + "-" + ((pd.to_datetime(days.date).dt.dayofyear - 1) // 7).astype(str)
)

# Require every candidate to predict the same held-out truths.
matching = days.groupby(["english_name", "date", "fold", "gap"]).agg(
    models=("model", "nunique"), truths=("count", "nunique")
)
assert days.english_name.nunique() == 16
assert (matching.models == 6).all() and (matching.truths == 1).all()
assert (days.groupby(keys).weather_group.nunique() == 1).all()
reconciled = (
    hours.groupby(["english_name", "model", "fold", "date"], as_index=False)
    .agg(count=("count", "sum"), predicted=("predicted", "sum"))
    .merge(activity_days, on=["english_name", "model", "fold", "date"], suffixes=("_hour", "_day"))
)
assert (reconciled.count_hour == reconciled.count_day).all()
assert np.allclose(reconciled.predicted_hour, reconciled.predicted_day, atol=1e-6)

scores = days.groupby(["english_name", "model", "gap", "weather_group"], as_index=False).agg(
    days=("count", "size"),
    mae=(
        "predicted",
        lambda prediction: np.mean(np.abs(prediction - days.loc[prediction.index, "count"])),
    ),
    actual=("count", "sum"),
    predicted=("predicted", "sum"),
)
scores["bias_fraction"] = scores.predicted / scores.actual - 1
production = scores.loc[
    scores.model.eq("production_episode"), ["english_name", "gap", "weather_group", "mae"]
].rename(columns={"mae": "production_mae"})
gamma = scores.loc[
    scores.model.eq("gamma_day_flocks"), ["english_name", "gap", "weather_group", "mae"]
].rename(columns={"mae": "gamma_mae"})
scores = scores.merge(production, on=["english_name", "gap", "weather_group"]).merge(
    gamma, on=["english_name", "gap", "weather_group"]
)
scores["production_mae_ratio"] = scores.mae / scores.production_mae
scores["gamma_mae_ratio"] = scores.mae / scores.gamma_mae
scores.to_csv(OUTPUT / "species_scores.csv", index=False)
macro = scores.groupby(["model", "gap", "weather_group"], as_index=False).agg(
    species=("english_name", "nunique"),
    mean_production_mae_ratio=("production_mae_ratio", "mean"),
    median_production_mae_ratio=("production_mae_ratio", "median"),
    species_better_than_production=("production_mae_ratio", lambda ratio: int((ratio < 1).sum())),
    mean_gamma_mae_ratio=("gamma_mae_ratio", "mean"),
    species_better_than_gamma=("gamma_mae_ratio", lambda ratio: int((ratio < 1).sum())),
    mean_absolute_bias=("bias_fraction", lambda bias: float(np.mean(np.abs(bias)))),
)
macro.to_csv(OUTPUT / "species_balanced_scores.csv", index=False)

# Resample calendar weeks jointly across species, then average species MAE differences.
rng = np.random.default_rng(20261011)
paired = (
    days.loc[
        days.model.isin(
            [
                "weather_activity",
                "shared_weather_activity",
                "gamma_day_flocks",
                "production_episode",
            ]
        )
    ]
    .pivot(
        index=["english_name", "date", "fold", "gap", "weather_group", "block", "count"],
        columns="model",
        values="predicted",
    )
    .reset_index()
)
bootstrap, macro_bootstrap = [], []
for (gap, weather), rows in paired.groupby(["gap", "weather_group"]):
    blocks = sorted(rows.block.unique())
    species = sorted(rows.english_name.unique())
    frequency = rng.multinomial(len(blocks), np.repeat(1 / len(blocks), len(blocks)), size=2000)
    for candidate in ["weather_activity", "shared_weather_activity"]:
        for reference in ["gamma_day_flocks", "production_episode"]:
            difference = np.abs(rows[candidate] - rows["count"]) - np.abs(
                rows[reference] - rows["count"]
            )
            clustered = (
                rows.assign(difference=difference)
                .groupby(["english_name", "block"])
                .agg(difference_sum=("difference", "sum"), n=("difference", "size"))
            )
            sums = (
                clustered.difference_sum.unstack()
                .reindex(index=species, columns=blocks)
                .fillna(0)
                .to_numpy()
            )
            counts = (
                clustered.n.unstack().reindex(index=species, columns=blocks).fillna(0).to_numpy()
            )
            denominators = frequency @ counts.T
            assert (denominators > 0).all()
            boot = (frequency @ sums.T) / denominators
            point = sums.sum(axis=1) / counts.sum(axis=1)
            for i, name in enumerate(species):
                bootstrap.append(
                    dict(
                        english_name=name,
                        candidate=candidate,
                        gap=gap,
                        weather_group=weather,
                        reference=reference,
                        mae_difference=point[i],
                        lower=np.nanquantile(boot[:, i], 0.025),
                        upper=np.nanquantile(boot[:, i], 0.975),
                    )
                )
            panel = boot.mean(axis=1)
            macro_bootstrap.append(
                dict(
                    candidate=candidate,
                    gap=gap,
                    weather_group=weather,
                    reference=reference,
                    species=len(species),
                    weeks=len(blocks),
                    mae_difference=point.mean(),
                    lower=np.quantile(panel, 0.025),
                    upper=np.quantile(panel, 0.975),
                )
            )
paired_scores = pd.DataFrame(bootstrap)
paired_scores.to_csv(OUTPUT / "paired_mae_differences.csv", index=False)
macro_paired = pd.DataFrame(macro_bootstrap)
macro_paired.to_csv(OUTPUT / "macro_paired_mae_differences.csv", index=False)

# Calibrate the probability of any birds separately from positive-count size.
hours["observed_active"] = hours["count"] > 0
hours["rain_band"] = pd.cut(
    hours.rain_mm,
    [-np.inf, 0.1, 1, 3, np.inf],
    labels=["<0.1", "0.1-1", "1-3", ">=3"],
    right=False,
)
activity = hours.loc[hours.model.isin(["weather_activity", "shared_weather_activity"])].copy()
activity["brier"] = (activity.active_probability - activity.observed_active.astype(float)) ** 2
calibration = activity.groupby(["model", "rain_band"], observed=True, as_index=False).agg(
    held_out_hours=("count", "size"),
    observed_active_fraction=("observed_active", "mean"),
    predicted_active_fraction=("active_probability", "mean"),
    brier_score=("brier", "mean"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
)
calibration.to_csv(OUTPUT / "activity_calibration.csv", index=False)
activity_diagnostics.to_csv(OUTPUT / "fit_diagnostics.csv", index=False)
shared_diagnostics.to_csv(OUTPUT / "shared_fit_diagnostics.csv", index=False)
print(macro.to_string(index=False))
print("\nHeld-out activity calibration by rain band")
print(calibration.to_string(index=False))
print("\nWeekly paired MAE differences; negative favours the candidate")
print(macro_paired.to_string(index=False))
print("\nSpecies-panel matching, count conservation and held-out aggregation checks passed")
