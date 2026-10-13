"""Assess the prespecified historical episode screen without selecting more candidates."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/history-episode")
manifest = pd.read_csv(OUT / "design/manifest.csv")
frames, diagnostics = [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    frame = pd.read_csv(folder / "assessment.csv")
    frames.append(frame)
    diagnostics.append(pd.read_csv(folder / "episode_diagnostics.csv"))
wide = pd.concat(frames, ignore_index=True)
assert len(manifest) == 40 and wide.groupby("task").english_name.nunique().eq(10).all()
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
)
reference = pd.read_csv("logs/historical-counts/predictions.csv")
reference = reference[reference.fold.eq(2) & reference.method.eq("original_episode")]
recent = pd.read_csv("logs/history-diagnosis/current_recent_predictions.csv")
recent = recent[recent.method.eq("original_episode")]
reference = pd.concat([reference.assign(task="historical"), recent.assign(task="recent")])
wide = wide.merge(
    reference[["date", "task", "english_name", "fold", "count", "predicted"]],
    on=["date", "task", "english_name", "fold"],
    validate="one_to_one",
    how="left",
    suffixes=("", "_original"),
)
assert np.allclose(wide["count"], wide.count_original)
assert wide.predicted.notna().all()
wide = wide.rename(columns={"predicted": "original_episode"})
long = wide.melt(
    id_vars=["date", "task", "english_name", "fold", "count", "weather", "year"],
    value_vars=["weather_mean", "weather_episode", "original_episode"],
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
species["episode_ratio"] = species.weather_episode / species.weather_mean
species.to_csv(OUT / "species_scores.csv")
scores = species.groupby(["task", "weather"])[
    ["weather_mean", "weather_episode", "original_episode"]
].mean()
scores["episode_ratio"] = scores.weather_episode / scores.weather_mean
scores.to_csv(OUT / "group_scores.csv")
summary.groupby(
    ["task", "era", "weather", "english_name", "method"], observed=True
).absolute_error.mean().groupby(["task", "era", "weather", "method"], observed=True).mean().to_csv(
    OUT / "era_scores.csv"
)
summary.groupby(
    ["task", "year", "weather", "english_name", "method"]
).absolute_error.mean().groupby(["task", "year", "weather", "method"]).mean().to_csv(
    OUT / "year_scores.csv"
)

# Resample shared historical years or recent calendar weeks across all species.
wide["difference"] = abs(wide.weather_episode - wide["count"]) - abs(
    wide.weather_mean - wide["count"]
)
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
    grouped = frame.groupby(["english_name", "block"]).difference.agg(["sum", "count"])
    sums = grouped["sum"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
    counts = grouped["count"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
    differences = ((weights @ sums.T) / (weights @ counts.T)).mean(axis=1)
    assert np.isfinite(differences).all()
    paired.append(
        dict(
            task=task,
            weather=weather,
            difference=frame.groupby("english_name").difference.mean().mean(),
            low=np.quantile(differences, 0.025),
            high=np.quantile(differences, 0.975),
            resampling_unit="year" if task == "historical" else "calendar_week",
        )
    )
pd.DataFrame(paired).to_csv(OUT / "paired_scores.csv", index=False)

# Reconstruction refers to eligible recorded intervals, not unknown seasonal truth.
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
season.groupby(["english_name", "method"]).absolute_relative_error.mean().groupby(
    "method"
).mean().to_csv(OUT / "season_scores.csv")
diagnostics = pd.concat(diagnostics, ignore_index=True)
assert diagnostics.gradient.lt(0.001).all() and diagnostics.derivative_error.lt(0.001).all()
diagnostics.to_csv(OUT / "diagnostics.csv", index=False)
runtime = diagnostics.pivot(index="key", columns="method", values="seconds")
runtime["ratio"] = runtime.weather_episode / runtime.weather_mean
runtime.to_csv(OUT / "runtime.csv")
gates = [
    dict(
        gate="historical_dry_5_percent_gain",
        passed=scores.loc[("historical", "dry"), "episode_ratio"] <= 0.95,
    ),
    dict(
        gate="historical_wet_2_percent_limit",
        passed=scores.loc[("historical", "wet"), "episode_ratio"] <= 1.02,
    ),
    dict(
        gate="recent_dry_2_percent_limit",
        passed=scores.loc[("recent", "dry"), "episode_ratio"] <= 1.02,
    ),
    dict(
        gate="recent_wet_2_percent_limit",
        passed=scores.loc[("recent", "wet"), "episode_ratio"] <= 1.02,
    ),
    dict(gate="median_final_fit_5_seconds", passed=runtime.weather_episode.median() <= 5),
    dict(gate="median_final_fit_5_times_baseline", passed=runtime.ratio.median() <= 5),
]
pd.DataFrame(gates).to_csv(OUT / "acceptance.csv", index=False)
print(scores.to_string())
print(pd.DataFrame(paired).to_string(index=False))
print(
    "Final-fit median seconds:",
    runtime.weather_mean.median(),
    runtime.weather_episode.median(),
    "median paired ratio:",
    runtime.ratio.median(),
)
print(pd.DataFrame(gates).to_string(index=False))
