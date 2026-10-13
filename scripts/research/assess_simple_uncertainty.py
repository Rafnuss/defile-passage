"""Assess empirical uncertainty and retained-hour shrinkage with the mean model frozen."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import diags
from simple_rate_model import fit_rate
from simple_rate_prediction import (
    LEVELS,
    count_interval,
    retained_prediction,
    select_retained_strength,
    short_gap_mask,
)

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--prefix", default="gap-validation")
parser.add_argument("--out", type=Path, default=ROOT / "logs/simple-uncertainty")
parser.add_argument("--operational", action="store_true")
args = parser.parse_args()
OUT = args.out
OUT.mkdir(exist_ok=True)
calibrations, predictions, diagnostics = [], [], []
for panel in ["priority", "passerines"]:
    design = ROOT / f"logs/{args.prefix}-design-{panel}"
    manifest = pd.read_csv(design / "manifest.csv")
    for context in manifest.itertuples():
        started = perf_counter()
        key = context.key
        rows = pd.read_csv(design / f"{key}_components.csv")
        observations = pd.read_csv(design / f"{key}_observations.csv")
        assert np.array_equal(rows.observation_id, observations.observation_id)
        X = np.loadtxt(design / f"{key}_year_weather_X.csv", delimiter=",")
        penalty = np.loadtxt(design / f"{key}_year_weather_penalty.csv", delimiter=",")
        fit = np.load(ROOT / f"logs/{args.prefix}-{panel}/year_weather/{key}/{key}_fit.npz")
        assert X.shape[1] == 22 and fit["variance_power"] == 1.5
        ridge = np.zeros_like(penalty)
        linear = [1, 15, 16, 17, 18, 19, 20, 21]
        ridge[linear, linear] = 1
        penalty = float(fit["smoothing"]) * penalty + ridge
        A = diags(rows.fraction.to_numpy(), format="csr")
        hidden = rows.hidden.to_numpy()
        dates = pd.to_datetime(rows.date)
        weeks = ((dates - pd.Timestamp("1970-01-05")).dt.days // 7).to_numpy()
        rows["mean"] = A @ np.exp(X @ fit["coefficients"])
        rows["calibration_mean"] = np.nan
        rows["short_gap"] = short_gap_mask(rows)
        gradients = []
        for fold in range(3):
            held = ~hidden & (weeks % 3 == fold)
            if args.operational:
                held = ~rows.target_day.to_numpy() & (weeks % 3 == fold)
                train = ~hidden & ~(held & rows.short_gap.to_numpy())
            else:
                train = ~hidden & ~held
            result, _ = fit_rate(X, A[train], rows.loc[train, "count"].to_numpy(), penalty, 1.5)
            gradients.append(np.abs(result.jac).max())
            assert gradients[-1] < 0.001, (key, fold, gradients[-1])
            rows.loc[held, "calibration_mean"] = A[held] @ np.exp(X @ result.x)
        rows["rain_exposure"] = rows.rain_mm * rows.exposure_hours
        daily = rows.groupby("date").agg(
            count=("count", "sum"),
            mean=("mean", "sum"),
            calibration_mean=("calibration_mean", "sum"),
            hidden=("target_day" if args.operational else "hidden", "first"),
            rain_exposure=("rain_exposure", "sum"),
            exposure_hours=("exposure_hours", "sum"),
        )
        daily["weather"] = np.where(
            daily.rain_exposure / daily.exposure_hours >= 0.1, "wet", "dry"
        )
        daily["week_fold"] = (
            (pd.to_datetime(daily.index) - pd.Timestamp("1970-01-05")).days // 7
        ) % 3
        daily["score"] = (
            abs(daily["count"] - daily.calibration_mean) / (daily.calibration_mean + 1) ** 0.75
        )
        calibration = daily[~daily.hidden].copy()
        if not args.operational:
            target = daily[daily.hidden].copy()
            target["task"], target["method"], target["predicted"] = (
                "full_day",
                "unadjusted",
                target["mean"],
            )
            for level in LEVELS:
                suffix = str(round(level * 100))
                target[f"lower{suffix}"], target[f"upper{suffix}"] = count_interval(
                    target.predicted, calibration.score, level
                )
            target["english_name"], target["fold"] = context.english_name, context.fold
            predictions.append(target.reset_index())
            calibrations.append(
                calibration.reset_index().assign(
                    english_name=context.english_name, fold=context.fold, task="full_day"
                )
            )
        # Sum the actual selected effort; never divide an intact observation's count.
        short = (
            rows[rows.short_gap]
            .groupby("date")
            .agg(
                missing_count=("count", "sum"),
                missing_mean=("mean", "sum"),
                calibration_missing_mean=("calibration_mean", "sum"),
                gap_hours=("exposure_hours", "sum"),
                gap_rain=("rain_exposure", "sum"),
            )
        )
        short = daily.join(short, how="inner")
        short["weather"] = np.where(short.gap_rain / short.gap_hours >= 0.1, "wet", "dry")
        short["retained_count"] = short["count"] - short.missing_count
        short["retained_mean"] = short["mean"] - short.missing_mean
        cal = short[~short.hidden].copy()
        cal["missing_mean"] = cal.calibration_missing_mean
        cal["retained_mean"] = cal.calibration_mean - cal.calibration_missing_mean
        strength = select_retained_strength(cal)
        cal["adjusted"] = np.nan
        for fold in range(3):
            held = cal.week_fold.eq(fold)
            inner_strength = select_retained_strength(cal[~held])
            cal.loc[held, "adjusted"] = retained_prediction(
                cal.loc[held, "missing_mean"],
                cal.loc[held, "retained_mean"],
                cal.loc[held, "retained_count"],
                inner_strength,
            )
        calibration_state = dict(strength=strength)
        if not args.operational:
            calibration_state["full_scores"] = calibration.score.to_numpy()
        for method in ["unadjusted", "retained_adjusted"]:
            point = cal.missing_mean if method == "unadjusted" else cal.adjusted
            scores = abs(cal.missing_count - point) / (point + 1) ** 0.75
            calibration_state[method + "_scores"] = scores.to_numpy()
            target = short[short.hidden].copy()
            target["predicted"] = (
                target.missing_mean
                if method == "unadjusted"
                else retained_prediction(
                    target.missing_mean, target.retained_mean, target.retained_count, strength
                )
            )
            target["full_observed_count"] = target["count"]
            target["count"] = target.missing_count
            target["task"], target["method"] = "three_hour_gap", method
            target["full_day_predicted"] = target.retained_count + target.predicted
            for level in LEVELS:
                suffix = str(round(level * 100))
                target[f"lower{suffix}"], target[f"upper{suffix}"] = count_interval(
                    target.predicted, scores, level
                )
                target[f"full_day_lower{suffix}"] = (
                    target.retained_count + target[f"lower{suffix}"]
                )
                target[f"full_day_upper{suffix}"] = (
                    target.retained_count + target[f"upper{suffix}"]
                )
            target["english_name"], target["fold"] = context.english_name, context.fold
            predictions.append(target.reset_index())
        np.savez(OUT / f"{key}_calibration.npz", **calibration_state)
        calibrations.append(
            cal.reset_index().assign(
                english_name=context.english_name, fold=context.fold, task="three_hour_gap"
            )
        )
        diagnostics.append(
            dict(
                key=key,
                english_name=context.english_name,
                fold=context.fold,
                strength=strength,
                seconds=perf_counter() - started,
                gradient=max(gradients),
                calibration_days=len(calibration),
                short_calibration_days=len(cal),
                short_test_days=int(short.hidden.sum()),
            )
        )
pd.concat(calibrations, ignore_index=True).to_csv(OUT / "calibration.csv", index=False)
pd.DataFrame(diagnostics).to_csv(OUT / "diagnostics.csv", index=False)
results = pd.concat(predictions, ignore_index=True)
results["assessment_group"] = np.select(
    [
        results.english_name.isin(["Common Wood Pigeon", "Stock Dove"]),
        results.english_name.isin(
            ["Barn Swallow", "Eurasian Chaffinch", "Meadow Pipit", "Redwing"]
        ),
    ],
    ["pigeons", "passerines"],
    default="core_large_birds",
)
results["absolute_error"] = abs(results["count"] - results.predicted)
results["zero"] = results["count"].eq(0)
for level in LEVELS:
    suffix = str(round(level * 100))
    lower, upper = results[f"lower{suffix}"], results[f"upper{suffix}"]
    results[f"covered{suffix}"] = results["count"].between(lower, upper)
    results[f"width{suffix}"] = upper - lower
    results[f"interval_score{suffix}"] = (
        upper
        - lower
        + 2
        / (1 - level)
        * ((lower - results["count"]).clip(lower=0) + (results["count"] - upper).clip(lower=0))
    )
results.to_csv(OUT / "predictions.csv", index=False)
summary = pd.concat([results, results.assign(weather="all")], ignore_index=True)
metrics = [
    "absolute_error",
    "covered80",
    "covered95",
    "width80",
    "width95",
    "interval_score80",
    "interval_score95",
]
species = summary.groupby(["assessment_group", "task", "method", "weather", "english_name"])[
    metrics
].mean()
species.to_csv(OUT / "species_scores.csv")
macro = species.groupby(["assessment_group", "task", "method", "weather"]).mean()
macro.to_csv(OUT / "group_scores.csv")
length_species = summary.groupby(
    ["assessment_group", "task", "method", "weather", "fold", "english_name"]
)[metrics].mean()
length_species.to_csv(OUT / "species_gap_length_scores.csv")
length_species.groupby(["assessment_group", "task", "method", "weather", "fold"]).mean().to_csv(
    OUT / "gap_length_scores.csv"
)
summary[summary.zero].groupby(["assessment_group", "task", "method", "weather"])[
    metrics + ["predicted"]
].mean().to_csv(OUT / "zero_scores.csv")
print(macro.to_string())
print(pd.DataFrame(diagnostics)[["seconds", "gradient"]].agg(["median", "max"]).to_string())
