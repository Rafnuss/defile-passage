"""Score actual historical holdouts, preserving species/year failures and coverage."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/historical-counts")
manifest = pd.read_csv(OUT / "input/manifest.csv")
predictions, totals, diagnostics, failures = [], [], [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    if not (folder / "assessment.csv").exists():
        failures.append(
            dict(key=context.key, english_name=context.english_name, fold=context.fold)
        )
        continue
    predictions.append(pd.read_csv(folder / "assessment.csv"))
    totals.append(pd.read_csv(folder / "season_totals.csv"))
    diagnostics.append(pd.read_csv(folder / "diagnostics.csv"))
pd.DataFrame(failures, columns=["key", "english_name", "fold"]).to_csv(
    OUT / "failures.csv", index=False
)
results = pd.concat(predictions, ignore_index=True).melt(
    id_vars=[
        "date",
        "count",
        "hours",
        "rain_hours",
        "retained_count",
        "retained_hours",
        "weather",
        "year",
        "english_name",
        "fold",
        "c",
    ],
    value_vars=["weather_mean", "original_episode"],
    var_name="method",
    value_name="predicted",
)
results["error"] = results.predicted - results["count"]
results["absolute_error"] = abs(results.error)
results["era"] = pd.cut(
    results.year, [1992, 2007, 2016, 2021], labels=["1993–2007", "2008–2016", "2017–2021"]
)
results["retained_fraction"] = results.retained_hours / (results.retained_hours + results.hours)
results["retained_coverage"] = pd.cut(
    results.retained_fraction, [-0.001, 0, 0.5, 1], labels=["none", "up to half", "more than half"]
)
results.to_csv(OUT / "predictions.csv", index=False)
results.groupby(
    ["era", "fold", "retained_coverage", "weather", "method", "english_name"], observed=True
)[["absolute_error", "error"]].mean().groupby(
    ["era", "fold", "retained_coverage", "weather", "method"], observed=True
).mean().to_csv(
    OUT / "coverage_gap_scores.csv"
)
summary = pd.concat([results, results.assign(weather="all")], ignore_index=True)
species = summary.groupby(["era", "fold", "weather", "method", "english_name"], observed=True)[
    ["absolute_error", "error"]
].mean()
species.to_csv(OUT / "species_gap_scores.csv")
species.groupby(["era", "fold", "weather", "method"], observed=True).mean().to_csv(
    OUT / "group_gap_scores.csv"
)
results.groupby(["year", "fold", "method", "english_name"])[
    ["absolute_error", "error"]
].mean().to_csv(OUT / "year_gap_scores.csv")
season = pd.concat(totals, ignore_index=True)
# Years without held-out observations are not validation successes.
active = pd.concat(predictions, ignore_index=True)[
    ["year", "english_name", "fold"]
].drop_duplicates()
season = season.merge(active, on=["year", "english_name", "fold"], validate="one_to_one")
frames = []
for method in ["weather_mean", "original_episode"]:
    sample = season[
        ["year", "english_name", "fold", "observed_truth", "truth_hours", "truth_dates"]
    ].copy()
    sample["method"] = method
    sample["bias"] = season[method + "_bias"]
    sample["reconstructed"] = season[method + "_reconstructed"]
    # Zero observed seasonal counts have no relative-error denominator; retain their absolute errors.
    sample["relative_bias"] = sample.bias / sample.observed_truth.where(
        sample.observed_truth.gt(0)
    )
    sample["absolute_relative_bias"] = abs(sample.relative_bias)
    frames.append(sample)
season = pd.concat(frames, ignore_index=True)
season["era"] = pd.cut(
    season.year, [1992, 2007, 2016, 2021], labels=["1993–2007", "2008–2016", "2017–2021"]
)
season.to_csv(OUT / "season_totals.csv", index=False)
season.groupby(["era", "fold", "method"], observed=True).agg(
    mean_relative_bias=("relative_bias", "mean"),
    mean_absolute_relative_bias=("absolute_relative_bias", "mean"),
    median_absolute_relative_bias=("absolute_relative_bias", "median"),
    species=("english_name", "nunique"),
    years=("year", "nunique"),
).to_csv(OUT / "season_scores.csv")
np.random.seed(20261012)
paired = []
for (era, fold), sample in season.groupby(["era", "fold"], observed=True):
    table = sample.pivot(
        index=["year", "english_name"], columns="method", values="absolute_relative_bias"
    )
    difference = (
        (table.weather_mean - table.original_episode).groupby("year").mean().dropna().to_numpy()
    )
    bootstrap = np.random.choice(difference, (4000, len(difference)), replace=True).mean(axis=1)
    paired.append(
        dict(
            era=era,
            fold=fold,
            difference=difference.mean(),
            lower=np.quantile(bootstrap, 0.025),
            upper=np.quantile(bootstrap, 0.975),
            years=len(difference),
        )
    )
pd.DataFrame(paired).to_csv(OUT / "paired_season_scores.csv", index=False)
pd.concat(diagnostics, ignore_index=True).to_csv(OUT / "diagnostics.csv", index=False)
print("Passed", len(diagnostics), "of", len(manifest), "; missing/failed:", len(failures))
print(pd.read_csv(OUT / "season_scores.csv").to_string(index=False))
