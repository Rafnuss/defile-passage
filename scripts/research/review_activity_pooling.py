"""Compare pooling with an integration-matched baseline on identical held-out truths."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
parser.add_argument("--out", type=Path, default=ROOT / "logs/activity-pooling-review")
args = parser.parse_args()
OUT = args.out
OUT.mkdir(parents=True, exist_ok=True)
frames, day_frames = [], []
for variant, prefix in [("adaptive", "adaptive-activity"), ("pooled", "pooled-activity")]:
    for panel in args.panels:
        for validation, suffix in [("blocked", ""), ("year", "-year")]:
            folder = ROOT / f"logs/{prefix}-{panel}{suffix}"
            frames.append(
                pd.read_csv(folder / "shared_activity_held_out_hours.csv").assign(
                    variant=variant, validation=validation
                )
            )
            day_frames.append(
                pd.read_csv(folder / "shared_activity_held_out_days.csv").assign(
                    variant=variant, validation=validation
                )
            )
hours, days = pd.concat(frames, ignore_index=True), pd.concat(day_frames, ignore_index=True)
for frame, scale, keys in [
    (hours, "hour", ["english_name", "fold", "start", "end"]),
    (days, "day", ["english_name", "fold", "date"]),
]:
    baseline = frame[frame.variant.eq("adaptive")][keys + ["count", "predicted", "rain_mm"]]
    candidate = frame[frame.variant.eq("pooled")].merge(
        baseline, on=keys, suffixes=("", "_baseline"), validate="one_to_one"
    )
    assert np.array_equal(candidate["count"], candidate.count_baseline)
    assert np.allclose(candidate.rain_mm, candidate.rain_mm_baseline)
    candidate["weather"] = np.where(candidate.rain_mm >= 0.1, "wet", "dry")
    candidate["error"] = abs(candidate.predicted - candidate["count"])
    candidate["baseline_error"] = abs(candidate.predicted_baseline - candidate["count"])
    candidate["coverage95"] = candidate["count"].between(candidate.q025, candidate.q975)
    candidate["width95"] = candidate.q975 - candidate.q025
    candidate["interval_score95"] = (
        candidate.width95
        + 40 * np.maximum(candidate.q025 - candidate["count"], 0)
        + 40 * np.maximum(candidate["count"] - candidate.q975, 0)
    )
    species = candidate.groupby(
        ["validation", "gap", "year", "weather", "english_name"], as_index=False
    ).agg(
        mae=("error", "mean"),
        baseline_mae=("baseline_error", "mean"),
        coverage95=("coverage95", "mean"),
        width95=("width95", "mean"),
        interval_score95=("interval_score95", "mean"),
    )
    species["mae_ratio"] = species.mae / species.baseline_mae
    species.to_csv(OUT / f"{scale}_species_scores.csv", index=False)
    summary = species.groupby(["validation", "gap", "year", "weather"], as_index=False).agg(
        mean_mae_ratio=("mae_ratio", "mean"),
        coverage95=("coverage95", "mean"),
        width95=("width95", "mean"),
        interval_score95=("interval_score95", "mean"),
    )
    summary.to_csv(OUT / f"{scale}_panel_scores.csv", index=False)
    print(scale, summary.to_string(index=False), sep="\n")
# Whole-day folds do not overlap each other; partial-day fold 3 is kept separate.
hours["task"] = np.where(
    hours.validation.eq("year"), "year", np.where(hours.fold.eq(3), "short_gap", "whole_day")
)
heavy = hours[hours.rain_mm.ge(3)].copy()
heavy["positive_error"] = abs(
    heavy.predictive_mean / heavy.predictive_active_probability - heavy["count"]
).where(heavy["count"].gt(0))
heavy["positive"] = heavy["count"].gt(0)
heavy.groupby(["variant", "task", "english_name"], as_index=False).agg(
    hours=("count", "size"),
    positive_hours=("positive", "sum"),
    observed_birds=("count", "sum"),
    predicted_birds=("predicted", "sum"),
    predictive_mean_birds=("predictive_mean", "sum"),
    positive_mae=("positive_error", "mean"),
).to_csv(OUT / "heavy_rain_species.csv", index=False)
print(
    "Heavy-rain totals",
    heavy.groupby(["variant", "task"])
    .agg(
        observed=("count", "sum"),
        predicted=("predicted", "sum"),
        positive_mae=("positive_error", "mean"),
    )
    .to_string(),
    sep="\n",
)

# Retain the matched production benchmark and paired calendar-week panel bootstrap.
references = [
    pd.read_csv(ROOT / "logs/hourly-weather-panel-v4/held_out_days.csv").assign(
        validation="blocked"
    )
]
for panel in args.panels:
    references.append(
        pd.read_csv(ROOT / f"logs/hourly-weather-{panel}-year/held_out_days.csv").assign(
            validation="year"
        )
    )
references = pd.concat(references, ignore_index=True)
references = references[references.model.isin(["production_episode", "gamma_day_flocks"])]
paired_rows, panel_intervals = [], []
rng = np.random.default_rng(20261012)
for variant in ["adaptive", "pooled"]:
    for reference in ["production_episode", "gamma_day_flocks"]:
        keys = ["english_name", "date", "fold", "gap", "validation"]
        comparison = days[days.variant.eq(variant)].merge(
            references[references.model.eq(reference)][keys + ["count", "predicted"]],
            on=keys,
            suffixes=("", "_reference"),
            validate="one_to_one",
        )
        assert np.array_equal(comparison["count"], comparison.count_reference)
        comparison["weather"] = np.where(comparison.rain_mm.ge(0.1), "wet", "dry")
        comparison["difference"] = abs(comparison.predicted - comparison["count"]) - abs(
            comparison.predicted_reference - comparison["count"]
        )
        comparison["block"] = (
            comparison.year.astype(str)
            + "-"
            + ((pd.to_datetime(comparison.date).dt.dayofyear - 1) // 7).astype(str)
        )
        for (validation, gap, weather), rows in comparison.groupby(
            ["validation", "gap", "weather"]
        ):
            blocks, species = sorted(rows.block.unique()), sorted(rows.english_name.unique())
            cluster = rows.groupby(["english_name", "block"]).agg(
                total=("difference", "sum"), n=("difference", "size")
            )
            sums = (
                cluster.total.unstack().reindex(index=species, columns=blocks).fillna(0).to_numpy()
            )
            counts = (
                cluster.n.unstack().reindex(index=species, columns=blocks).fillna(0).to_numpy()
            )
            frequency = rng.multinomial(
                len(blocks), np.repeat(1 / len(blocks), len(blocks)), size=2000
            )
            panel = ((frequency @ sums.T) / (frequency @ counts.T)).mean(axis=1)
            panel_intervals.append(
                dict(
                    variant=variant,
                    reference=reference,
                    validation=validation,
                    gap=gap,
                    weather=weather,
                    mae_difference=(sums.sum(axis=1) / counts.sum(axis=1)).mean(),
                    lower=np.quantile(panel, 0.025),
                    upper=np.quantile(panel, 0.975),
                )
            )
pd.DataFrame(panel_intervals).to_csv(OUT / "macro_paired_reference_scores.csv", index=False)
print(
    "Matched references; negative MAE differences favor the candidate",
    pd.DataFrame(panel_intervals).to_string(index=False),
    sep="\n",
)
