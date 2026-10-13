"""Separate current-input accuracy from the effect of historical weather terms."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/history-diagnosis")
current = OUT / "current-recent"
manifest = pd.read_csv(current / "input/manifest.csv")
frames, diagnostics = [], []
for context in manifest.itertuples():
    folder = current / "fits" / context.key
    frames.append(pd.read_csv(folder / "assessment.csv"))
    diagnostics.append(pd.read_csv(folder / "diagnostics.csv"))
a = pd.concat(frames).melt(
    id_vars=["date", "english_name", "fold", "count", "weather", "year"],
    value_vars=["original_episode", "weather_mean"],
    var_name="method",
    value_name="predicted",
)
a["error"] = a.predicted - a["count"]
a["absolute_error"] = abs(a.error)
a.to_csv(OUT / "current_recent_predictions.csv", index=False)
a = pd.concat([a, a.assign(weather="all")])
s = a.groupby(["english_name", "method", "weather"]).absolute_error.mean().unstack("method")
s["ratio"] = s.weather_mean / s.original_episode
s.to_csv(OUT / "current_recent_species_scores.csv")
s.groupby("weather").agg(
    original=("original_episode", "mean"),
    weather_model=("weather_mean", "mean"),
    median_ratio=("ratio", "median"),
    species_improved=("ratio", lambda x: (x < 1).sum()),
).to_csv(OUT / "current_recent_scores.csv")
clear = OUT / "historical-clear/fits"
assert pd.read_csv(clear / "status.csv").passed.all()
prediction = pd.read_csv(clear / "predictions.csv", low_memory=False)
prediction = (
    prediction.groupby(["date", "english_name", "fold"])[["count", "predicted"]]
    .sum()
    .reset_index()
)
base = pd.read_csv("logs/historical-counts/predictions.csv")
base = base[base.fold.lt(3)]
truth = base[base.method.eq("weather_mean")]
prediction = prediction.merge(
    truth[["date", "english_name", "fold", "year", "era", "weather", "count"]],
    on=["date", "english_name", "fold"],
    validate="one_to_one",
    suffixes=("", "_original"),
)
assert np.allclose(prediction["count"], prediction.count_original)
prediction["method"] = "no_weather"
prediction["error"] = prediction.predicted - prediction["count"]
prediction["absolute_error"] = abs(prediction.error)
all_methods = pd.concat([base, prediction], ignore_index=True)
all_methods["status"] = np.where(all_methods["count"].eq(0), "zero", "positive")
all_methods.to_csv(OUT / "historical_ablations.csv", index=False)
summary = pd.concat([all_methods, all_methods.assign(weather="all")], ignore_index=True)
summary.groupby(["english_name", "method", "weather"]).absolute_error.mean().groupby(
    ["method", "weather"]
).mean().to_csv(OUT / "historical_ablation_scores.csv")
summary.groupby(
    ["english_name", "era", "method", "weather", "status"]
).absolute_error.mean().groupby(
    ["era", "method", "weather", "status"], observed=True
).mean().to_csv(
    OUT / "historical_error_types.csv"
)
# Residual clustering on consecutive held-out dates is descriptive, not a component ablation.
base = base.copy()
base["date"] = pd.to_datetime(base.date)
base["residual"] = np.arcsinh(base["count"]) - np.arcsinh(base.predicted)
base = base.sort_values(["english_name", "year", "fold", "method", "date"])
groups = base.groupby(["english_name", "year", "fold", "method"])
base["previous"] = groups.residual.shift()
base["previous_date"] = groups.date.shift()
base = base[(base.date - base.previous_date).dt.days.eq(1)]
correlation = (
    base.groupby(["era", "english_name", "method"])
    .apply(lambda x: x.residual.corr(x.previous), include_groups=False)
    .rename("correlation")
    .reset_index()
)
correlation.to_csv(OUT / "historical_residual_correlation.csv", index=False)
pd.concat(diagnostics).to_csv(OUT / "current_recent_diagnostics.csv", index=False)
print("Current recent inputs, matched benchmark:")
print(pd.read_csv(OUT / "current_recent_scores.csv").to_string(index=False))
print("Historical weather ablation:")
print(pd.read_csv(OUT / "historical_ablation_scores.csv").to_string(index=False))

# Refit ablations retain the original benchmark's other components and fitting rules.
frames = [pd.read_csv(p) for p in (OUT / "benchmark-time").glob("*/assessment.csv")]
time = pd.concat(frames, ignore_index=True)
assert time.english_name.nunique() == 10 and time.groupby("english_name").arm.nunique().eq(4).all()
time["error"] = time.predicted - time["count"]
time["absolute_error"] = abs(time.error)
time["era"] = pd.cut(
    time.year, [1992, 2007, 2016, 2021], labels=["1993–2007", "2008–2016", "2017–2021"]
)
time.to_csv(OUT / "benchmark_time_predictions.csv", index=False)
summary = pd.concat([time, time.assign(weather="all")], ignore_index=True)
summary.groupby(
    ["english_name", "era", "arm", "weather"], observed=True
).absolute_error.mean().groupby(["era", "arm", "weather"], observed=True).mean().to_csv(
    OUT / "benchmark_time_scores.csv"
)
