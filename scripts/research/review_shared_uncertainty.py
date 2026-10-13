"""Score joint predictive draws, year transfer and weather support separately."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--panels", nargs="+", choices=["priority", "passerines"], default=["priority", "passerines"]
)
parser.add_argument("--prefix", default="shared-uncertainty")
parser.add_argument("--out", type=Path, default=ROOT / "logs/shared-uncertainty-review")
args = parser.parse_args()
OUTPUT = args.out
OUTPUT.mkdir(parents=True, exist_ok=True)
hour_frames, day_frames, diagnostics, support = [], [], [], []
for validation, suffix in [("blocked", ""), ("year", "-year")]:
    for group in args.panels:
        folder = ROOT / f"logs/{args.prefix}-{group}{suffix}"
        prepared = ROOT / f"logs/hourly-weather-{group}{suffix}"
        hours = pd.read_csv(folder / "shared_activity_held_out_hours.csv")
        days = pd.read_csv(folder / "shared_activity_held_out_days.csv")
        hour_frames.append(hours.assign(validation=validation))
        day_frames.append(days.assign(validation=validation))
        diagnostics.append(
            pd.read_csv(folder / "shared_activity_fit_diagnostics.csv").assign(
                validation=validation, panel=group
            )
        )
        manifest = pd.read_csv(prepared / "manifest.csv").query(
            "fold >= 5" if suffix else "fold < 4"
        )
        for record in manifest.itertuples():
            samples = np.load(folder / f"{record.key}_predictive_draws.npz")
            summed = np.zeros_like(samples["daily_counts"])
            np.add.at(summed, samples["date_group"], samples["hourly_counts"])
            assert np.array_equal(summed, samples["daily_counts"])
            assert np.isfinite(summed).all() and (summed >= 0).all()
            training = pd.read_csv(prepared / f"{record.key}_train.csv")
            testing = pd.read_csv(prepared / f"{record.key}_test.csv")
            features = [
                "log_rain",
                "log_previous_rain",
                "wind_u_m_s",
                "wind_v_m_s",
                "radiation_100",
                "low_cloud_fraction",
            ]
            unique_weather = training[features].drop_duplicates()
            center, scale = unique_weather.mean(), unique_weather.std()
            train_weather = ((unique_weather - center) / scale).to_numpy()
            test_weather = ((testing[features] - center) / scale).to_numpy()
            tree = cKDTree(train_weather)
            cutoff = np.quantile(tree.query(train_weather, k=2)[0][:, 1], 0.95)
            unsupported = tree.query(test_weather)[0] > cutoff
            outside_range = (
                (testing[features] < training[features].min())
                | (testing[features] > training[features].max())
            ).any(axis=1)
            support.append(
                testing[
                    ["english_name", "year", "date", "start", "rain_mm", "exposure_hours"]
                ].assign(
                    validation=validation,
                    fold=record.fold,
                    unsupported_combination=unsupported,
                    outside_training_range=outside_range,
                )
            )
hours = pd.concat(hour_frames, ignore_index=True)
days = pd.concat(day_frames, ignore_index=True)
fits = pd.concat(diagnostics, ignore_index=True)
assert (
    len(fits) == sum(96 if panel == "priority" else 32 for panel in args.panels)
    and fits.converged.all()
)
assert (fits.gradient_check < 1e-3).all() and (fits.hessian_check < 1e-3).all()
fits["quadrature_flag"] = (fits.quadrature_loss_delta_per_day > 1e-3) | (
    fits.quadrature_gradient_delta > 0.01
)
fits.to_csv(OUTPUT / "fit_diagnostics.csv", index=False)

for frame, scale in [(hours, "hour"), (days, "day")]:
    frame["weather_group"] = np.where(frame.rain_mm >= 0.1, "wet", "dry")
    frame["coverage95"] = frame["count"].between(frame.q025, frame.q975)
    frame["coverage80"] = frame["count"].between(frame.q10, frame.q90)
    frame["width95"] = frame.q975 - frame.q025
    frame["interval_score95"] = (
        frame.width95
        + 40 * np.maximum(frame.q025 - frame["count"], 0)
        + 40 * np.maximum(frame["count"] - frame.q975, 0)
    )
    frame["absolute_error"] = (frame.predicted - frame["count"]).abs()
    scores = frame.groupby(
        ["validation", "english_name", "year", "gap", "weather_group"], as_index=False
    ).agg(
        observations=("count", "size"),
        actual_birds=("count", "sum"),
        predicted_birds=("predicted", "sum"),
        mae=("absolute_error", "mean"),
        coverage95=("coverage95", "mean"),
        coverage80=("coverage80", "mean"),
        mean_width95=("width95", "mean"),
        interval_score95=("interval_score95", "mean"),
    )
    scores.to_csv(OUTPUT / f"{scale}_species_year_scores.csv", index=False)
    macro = scores.groupby(["validation", "year", "gap", "weather_group"], as_index=False).agg(
        species=("english_name", "nunique"),
        coverage95=("coverage95", "mean"),
        coverage80=("coverage80", "mean"),
        mean_mae=("mae", "mean"),
        mean_interval_score95=("interval_score95", "mean"),
    )
    macro.to_csv(OUTPUT / f"{scale}_species_balanced_scores.csv", index=False)
    print(f"\n{scale}: species-balanced point and interval scores")
    print(macro.to_string(index=False))

hours["rain_band"] = pd.cut(
    hours.rain_mm,
    [-np.inf, 0.1, 1, 3, np.inf],
    labels=["<0.1", "0.1-1", "1-3", ">=3"],
    right=False,
)
hours["positive"] = hours["count"] > 0
hours["brier"] = (hours.predictive_active_probability - hours.positive.astype(float)) ** 2
hours["positive_log_score"] = (
    hours.log_score - np.log(hours.predictive_active_probability)
).where(hours.positive)
hours["observed_positive_count"] = hours["count"].where(hours.positive)
hours["predicted_positive_count"] = (
    hours.predictive_mean / hours.predictive_active_probability
).where(hours.positive)
calibration = hours.groupby(
    ["validation", "english_name", "year", "gap", "rain_band"], observed=True, as_index=False
).agg(
    observations=("count", "size"),
    positive_hours=("positive", "sum"),
    observed_active=("positive", "mean"),
    predicted_active=("predictive_active_probability", "mean"),
    brier=("brier", "mean"),
    unconditional_log_score=("log_score", "mean"),
    positive_log_score=("positive_log_score", "mean"),
    observed_positive_mean=("observed_positive_count", "mean"),
    predicted_positive_mean=("predicted_positive_count", "mean"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
    predictive_mean_birds=("predictive_mean", "sum"),
)
calibration.to_csv(OUTPUT / "occurrence_positive_calibration.csv", index=False)
weather = pd.concat(support, ignore_index=True)
weather["rain_band"] = pd.cut(
    weather.rain_mm,
    [-np.inf, 0.1, 1, 3, np.inf],
    labels=["<0.1", "0.1-1", "1-3", ">=3"],
    right=False,
)
weather.groupby(
    ["validation", "english_name", "year", "fold", "rain_band"], observed=True, as_index=False
).agg(
    test_hours=("exposure_hours", "sum"),
    unsupported_fraction=("unsupported_combination", "mean"),
    outside_range_fraction=("outside_training_range", "mean"),
).to_csv(
    OUTPUT / "weather_support.csv", index=False
)
print("\nConvergence, analytic gradients/Hessians and joint-draw conservation passed")
print(
    f"Quadrature sensitivity flagged in {fits.quadrature_flag.sum()} of {len(fits)} fits; flagged fits require refinement before use."
)
print(
    "Intervals condition on fitted Gamma/NB shapes and smoothing; weather error and shape/smoothing uncertainty are excluded."
)
