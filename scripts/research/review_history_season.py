"""Assess a paired mean-model control on matching historical and recent targets."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path("logs/history-season"))
parser.add_argument("--candidate", default="weather_season")
parser.add_argument("--allow-incomplete", action="store_true")
args = parser.parse_args()
OUT = args.root
candidate = args.candidate
ratio_column = {
    "weather_season": "season_ratio",
    "weather_weighted": "weight_ratio",
    "weather_separate": "smoothing_ratio",
}.get(candidate, "candidate_ratio")
manifest = pd.read_csv(OUT / "design/manifest.csv")
completed = manifest.key.map(
    lambda key: (OUT / "fits" / key / "assessment.csv").exists()
    and (OUT / "fits" / key / "diagnostics.csv").exists()
)
complete = completed.all()
assert complete or args.allow_incomplete, "Incomplete fits cannot pass acceptance."
if not complete:
    manifest[~completed].to_csv(OUT / "missing_contexts.csv", index=False)
    manifest = manifest[completed]
frames, diagnostics = [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    frames.append(pd.read_csv(folder / "assessment.csv"))
    diagnostics.append(pd.read_csv(folder / "diagnostics.csv"))
wide = pd.concat(frames, ignore_index=True)
assert (
    len(manifest) == 40 and wide.groupby("task").english_name.nunique().eq(10).all()
) or args.allow_incomplete
assert (
    wide.groupby(["task", "english_name"])
    .fold.nunique()
    .eq(
        wide.groupby(["task", "english_name"])
        .size()
        .index.get_level_values("task")
        .map({"historical": 1, "recent": 3})
    )
    .all()
    or args.allow_incomplete
)
base = pd.read_csv("logs/history-episode/predictions.csv")
original = base[base.method.eq("original_episode")]
wide = wide.merge(
    original[["date", "task", "english_name", "fold", "count", "predicted"]],
    on=["date", "task", "english_name", "fold"],
    how="left",
    validate="one_to_one",
    suffixes=("", "_original"),
)
assert np.allclose(wide["count"], wide.count_original) and wide.predicted.notna().all()
wide = wide.rename(columns={"predicted": "original_episode"})
long = wide.melt(
    id_vars=["date", "task", "english_name", "fold", "count", "weather", "year"],
    value_vars=["weather_mean", candidate, "original_episode"],
    var_name="method",
    value_name="predicted",
)
long["error"] = long.predicted - long["count"]
long["absolute_error"] = abs(long.error)
long["era"] = pd.cut(
    long.year,
    [1992, 2007, 2016, 2021, 2025],
    labels=["1993–2007", "2008–2016", "2017–2021", "2022–2025"],
)
long.to_csv(OUT / "predictions.csv", index=False)
summary = pd.concat([long, long.assign(weather="all")])
species = (
    summary.groupby(["task", "weather", "english_name", "method"])
    .absolute_error.mean()
    .unstack("method")
)
species[ratio_column] = species[candidate] / species.weather_mean
species.to_csv(OUT / "species_scores.csv")
scores = species.groupby(["task", "weather"])[
    ["weather_mean", candidate, "original_episode"]
].mean()
scores[ratio_column] = scores[candidate] / scores.weather_mean
scores.to_csv(OUT / "group_scores.csv")
era = (
    summary.groupby(["task", "era", "weather", "english_name", "method"], observed=True)
    .absolute_error.mean()
    .groupby(["task", "era", "weather", "method"], observed=True)
    .mean()
    .unstack("method")
)
era.to_csv(OUT / "era_scores.csv")
summary.groupby(
    ["task", "year", "weather", "english_name", "method"]
).absolute_error.mean().groupby(["task", "year", "weather", "method"]).mean().to_csv(
    OUT / "year_scores.csv"
)

# Shared year/week resampling retains cross-species dependence and equal species weights.
dates = pd.to_datetime(wide.date)
wide["block"] = np.where(
    wide.task.eq("historical"), wide.year, (dates - pd.Timestamp("1970-01-05")).dt.days // 7
)
paired = []
rng = np.random.default_rng(20261012)
for (task, weather), frame in pd.concat([wide, wide.assign(weather="all")]).groupby(
    ["task", "weather"]
):
    blocks = sorted(frame.block.unique())
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
    for reference in ["weather_mean", "original_episode"]:
        difference = abs(frame[candidate] - frame["count"]) - abs(
            frame[reference] - frame["count"]
        )
        grouped = (
            frame.assign(difference=difference)
            .groupby(["english_name", "block"])
            .difference.agg(["sum", "count"])
        )
        sums = grouped["sum"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        counts = grouped["count"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        draws = ((weights @ sums.T) / (weights @ counts.T)).mean(axis=1)
        assert np.isfinite(draws).all()
        paired.append(
            dict(
                task=task,
                weather=weather,
                reference=reference,
                difference=frame.assign(difference=difference)
                .groupby("english_name")
                .difference.mean()
                .mean(),
                low=np.quantile(draws, 0.025),
                high=np.quantile(draws, 0.975),
                resampling_unit="year" if task == "historical" else "calendar_week",
            )
        )
pd.DataFrame(paired).to_csv(OUT / "paired_scores.csv", index=False)
history = pd.read_csv("logs/historical-counts/observations.csv", low_memory=False)
truth = (
    history[history.training_eligible]
    .groupby(["english_name", "year"])["count"]
    .sum()
    .rename("observed_truth")
)
season = (
    long[long.task.eq("historical")]
    .groupby(["english_name", "year", "method"])
    .error.sum()
    .to_frame("bias")
    .join(truth)
)
season["absolute_relative_error"] = abs(season.bias) / season.observed_truth
season.to_csv(OUT / "season_errors.csv")
season_scores = (
    season.groupby(["english_name", "method"])
    .absolute_relative_error.mean()
    .groupby("method")
    .mean()
)
season_scores.to_csv(OUT / "season_scores.csv")
diagnostics = pd.concat(diagnostics, ignore_index=True)
assert diagnostics.gradient.lt(0.001).all() and diagnostics.derivative_error.lt(0.001).all()
diagnostics.to_csv(OUT / "diagnostics.csv", index=False)
runtime = diagnostics.pivot(index="key", columns="method", values="final_seconds")
runtime["ratio"] = runtime[candidate] / runtime.weather_mean
runtime.to_csv(OUT / "runtime.csv")
gates = [
    dict(
        gate="historical_dry_at_least_original",
        passed=scores.loc[("historical", "dry"), candidate]
        <= scores.loc[("historical", "dry"), "original_episode"],
    ),
    dict(
        gate="early_dry_at_least_original",
        passed=era.loc[("historical", "1993–2007", "dry"), candidate]
        <= era.loc[("historical", "1993–2007", "dry"), "original_episode"],
    ),
    dict(
        gate="season_error_at_least_original",
        passed=season_scores[candidate] <= season_scores.original_episode,
    ),
    dict(
        gate="historical_wet_2_percent_limit",
        passed=scores.loc[("historical", "wet"), ratio_column] <= 1.02,
    ),
    dict(
        gate="recent_dry_2_percent_limit",
        passed=scores.loc[("recent", "dry"), ratio_column] <= 1.02,
    ),
    dict(
        gate="recent_wet_2_percent_limit",
        passed=scores.loc[("recent", "wet"), ratio_column] <= 1.02,
    ),
    dict(gate="median_final_fit_5_seconds", passed=runtime[candidate].median() <= 5),
    dict(gate="median_final_fit_5_times_baseline", passed=runtime.ratio.median() <= 5),
]
if args.allow_incomplete:
    gates.insert(0, dict(gate="all_40_contexts_complete", passed=complete))
pd.DataFrame(gates).to_csv(OUT / "acceptance.csv", index=False)
print(scores.to_string())
print(era.to_string())
print(season_scores.to_string())
print(pd.DataFrame(paired).to_string(index=False))
print(
    "Median final seconds:",
    runtime.weather_mean.median(),
    runtime[candidate].median(),
    "paired ratio:",
    runtime.ratio.median(),
)
print(pd.DataFrame(gates).to_string(index=False))
