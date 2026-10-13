"""Assess intact survey counts, matched hourly truths and coherent daily uncertainty."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
parser.add_argument("--out", type=Path, default=ROOT / "logs/coherent-interval-review")
args = parser.parse_args()
OUT = args.out
OUT.mkdir(parents=True, exist_ok=True)
frames, fits = [], []
for panel in args.panels:
    folder = ROOT / f"logs/coherent-intervals-{panel}-year"
    frame = pd.read_csv(folder / "held_out_intervals.csv")
    support = []
    for context in pd.read_csv(ROOT / f"logs/mixed-design-{panel}-year/manifest.csv").itertuples():
        components = pd.read_csv(
            ROOT / f"logs/mixed-design-{panel}-year/{context.key}_components.csv"
        )
        bounds = components.groupby("observation_id", as_index=False).agg(
            min_tau=("tau", "min"), max_tau=("tau", "max")
        )
        bounds["english_name"], bounds["fold"] = context.english_name, context.fold
        support.append(bounds)
    frame = frame.merge(
        pd.concat(support), on=["english_name", "fold", "observation_id"], validate="one_to_one"
    )
    frame["outside_daylight_basis"] = frame.min_tau.lt(0) | frame.max_tau.gt(1)
    frame["panel"] = panel
    frames.append(frame)
    fits.append(pd.read_csv(folder / "fit_diagnostics.csv"))
observations, diagnostics = pd.concat(frames, ignore_index=True), pd.concat(
    fits, ignore_index=True
)
assert (
    len(diagnostics)
    == sum(
        len(pd.read_csv(ROOT / f"logs/mixed-design-{panel}-year/manifest.csv"))
        for panel in args.panels
    )
    and diagnostics.gradient.lt(1e-3).all()
    and diagnostics.gradient_check.lt(1e-3).all()
)
diagnostics["integration_flag"] = diagnostics.integration_loss_delta.ge(
    1e-3
) | diagnostics.integration_gradient_delta.ge(0.01)
diagnostics.to_csv(OUT / "fit_diagnostics.csv", index=False)
assert np.isfinite(observations.predicted).all() and observations.predicted.ge(0).all()
observations["occurrence_brier"] = (
    observations.active_probability - observations["count"].gt(0)
) ** 2
observations["year"] = pd.to_datetime(observations.date).dt.year
observations["absolute_error"] = abs(observations.predicted - observations["count"])
observations["baseline_error"] = abs(observations.baseline_predicted - observations["count"])
observations["coverage95"] = observations["count"].between(observations.q025, observations.q975)
observations["width95"] = observations.q975 - observations.q025
observations["interval_score95"] = (
    observations.width95
    + 40 * np.maximum(observations.q025 - observations["count"], 0)
    + 40 * np.maximum(observations["count"] - observations.q975, 0)
)
scores = observations.groupby(["english_name", "year", "resolution"], as_index=False).agg(
    observations=("count", "size"),
    birds=("count", "sum"),
    predicted=("predicted", "sum"),
    mae=("absolute_error", "mean"),
    baseline_mae=("baseline_error", "mean"),
    coverage95=("coverage95", "mean"),
    width95=("width95", "mean"),
    occurrence_brier=("occurrence_brier", "mean"),
    interval_score95=("interval_score95", "mean"),
)
scores.to_csv(OUT / "species_year_resolution_scores.csv", index=False)
observations.groupby(
    ["english_name", "year", "resolution", "outside_daylight_basis"], as_index=False
).agg(
    observations=("count", "size"),
    birds=("count", "sum"),
    predicted=("predicted", "sum"),
    max_prediction=("predicted", "max"),
    mae=("absolute_error", "mean"),
).to_csv(
    OUT / "daylight_extrapolation_scores.csv", index=False
)
# Match the previous hourly validation exactly, keeping intact coarse counts separate.
matched = []
for panel in args.panels:
    baseline = pd.read_csv(
        ROOT / f"logs/pooled-activity-{panel}-year/shared_activity_held_out_hours.csv"
    )
    rows = observations[observations.panel.eq(panel) & observations.resolution.eq("hour")].merge(
        baseline[["english_name", "fold", "start", "end", "count", "predicted", "rain_mm"]],
        on=["english_name", "fold", "start", "end"],
        suffixes=("", "_previous"),
        validate="one_to_one",
    )
    assert np.array_equal(rows["count"], rows.count_previous)
    rows["weather"] = np.where(rows.rain_mm.ge(0.1), "wet", "dry")
    rows["previous_error"] = abs(rows.predicted_previous - rows["count"])
    matched.append(rows)
matched = pd.concat(matched, ignore_index=True)
matched.groupby(["english_name", "year", "weather"], as_index=False).agg(
    hours=("count", "size"),
    mae=("absolute_error", "mean"),
    previous_mae=("previous_error", "mean"),
    coverage95=("coverage95", "mean"),
    interval_score95=("interval_score95", "mean"),
).to_csv(OUT / "matched_hourly_scores.csv", index=False)
# Daily point comparison on exactly the common hourly observation intervals.
matched["exposure"] = (
    pd.to_datetime(matched.end) - pd.to_datetime(matched.start)
).dt.total_seconds() / 3600
matched["rain_exposure"] = matched.rain_mm * matched.exposure
common_days = matched.groupby(["english_name", "fold", "date", "year"], as_index=False).agg(
    count=("count", "sum"),
    predicted=("predicted", "sum"),
    previous=("predicted_previous", "sum"),
    exposure=("exposure", "sum"),
    rain_exposure=("rain_exposure", "sum"),
)
common_days["weather"] = np.where(
    (common_days.rain_exposure / common_days.exposure).ge(0.1), "wet", "dry"
)
common_days["mae"] = abs(common_days.predicted - common_days["count"])
common_days["previous_mae"] = abs(common_days.previous - common_days["count"])
common_days.to_csv(OUT / "matched_daily_predictions.csv", index=False)
common_scores = common_days.groupby(["english_name", "year", "weather"], as_index=False).agg(
    days=("count", "size"), mae=("mae", "mean"), previous_mae=("previous_mae", "mean")
)
common_scores.to_csv(OUT / "matched_daily_scores.csv", index=False)
daily = observations.groupby(
    ["panel", "english_name", "fold", "date", "year"], as_index=False
).agg(count=("count", "sum"), predicted=("predicted", "sum"))
for (panel, species, fold), group in daily.groupby(["panel", "english_name", "fold"]):
    key = species.replace(" ", "_") + f"_fold{fold}"
    draws = np.load(ROOT / f"logs/coherent-intervals-{panel}-year/{key}_draws.npz")
    rows = observations[
        observations.panel.eq(panel)
        & observations.english_name.eq(species)
        & observations.fold.eq(fold)
    ]
    dates, groups = np.unique(rows.date, return_inverse=True)
    reconciled = np.zeros_like(draws["daily_counts"])
    np.add.at(reconciled, groups, draws["counts"])
    assert np.array_equal(dates.astype(str), draws["dates"])
    assert np.isfinite(draws["counts"]).all() and (draws["counts"] >= 0).all()
    np.testing.assert_array_equal(reconciled, draws["daily_counts"])
    quantiles = np.quantile(draws["daily_counts"], [0.025, 0.975], axis=1)
    for i, label in enumerate(["q025", "q975"]):
        daily.loc[group.index, label] = group.date.map(
            pd.Series(quantiles[i], index=draws["dates"])
        )
daily["coverage95"] = daily["count"].between(daily.q025, daily.q975)
daily["width95"] = daily.q975 - daily.q025
daily.to_csv(OUT / "held_out_daily_scores.csv", index=False)
print(
    scores.groupby("resolution")
    .agg(
        species=("english_name", "nunique"),
        observations=("observations", "sum"),
        observed_birds=("birds", "sum"),
        predicted_birds=("predicted", "sum"),
        mean_species_mae=("mae", "mean"),
        mean_coverage95=("coverage95", "mean"),
    )
    .to_string()
)
print(f"Integration flags: {diagnostics.integration_flag.sum()} / {len(diagnostics)}")
print(
    "Intervals include daily state, count variation and four calibration coefficients; base GAM/shape/dispersion uncertainty is excluded."
)
