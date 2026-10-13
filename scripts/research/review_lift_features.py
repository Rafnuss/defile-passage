"""Review the completed lift test and its matched radiation/cloud comparison."""

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/era5-lift")
ROOT = OUT / "lift"
PREVIOUS = Path("logs/era5-features/soaring")
with (OUT / "review.log").open("w") as log:
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/research/review_era5_features.py",
            "--root",
            str(OUT),
            "--variants",
            "lift",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
new = pd.read_csv(ROOT / "predictions.csv")
old = pd.read_csv(PREVIOUS / "predictions.csv")
keys = ["date", "task", "english_name", "fold", "weather", "year"]
new_truth = new[new.method.eq("weather_mean")].set_index(keys).sort_index()
old_truth = old[old.method.eq("weather_mean")].set_index(keys).sort_index()
assert new_truth.index.equals(old_truth.index)
assert np.allclose(
    new_truth[["count", "predicted"]], old_truth[["count", "predicted"]], atol=1e-5, rtol=1e-5
)
long = pd.concat([new, old[old.method.eq("weather_soaring")]], ignore_index=True)
long.to_csv(OUT / "comparison_predictions.csv", index=False)
summary = pd.concat([long, long.assign(weather="all")])
summary.groupby(["task", "weather", "english_name", "method"]).absolute_error.mean().groupby(
    ["task", "weather", "method"]
).mean().unstack("method").to_csv(OUT / "comparison_scores.csv")
wide = long.pivot(index=keys, columns="method", values="predicted").reset_index()
wide = wide.merge(
    new[new.method.eq("weather_mean")][keys + ["count"]], on=keys, validate="one_to_one"
)
dates = pd.to_datetime(wide.date)
wide["block"] = np.where(
    wide.task.eq("historical"), wide.year, (dates - pd.Timestamp("1970-01-05")).dt.days // 7
)
rng = np.random.default_rng(20261012)
paired = []
for (task, weather), frame in pd.concat([wide, wide.assign(weather="all")]).groupby(
    ["task", "weather"]
):
    blocks = sorted(frame.block.unique())
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
    frame = frame.assign(
        difference=abs(frame.weather_lift - frame["count"])
        - abs(frame.weather_soaring - frame["count"])
    )
    grouped = frame.groupby(["english_name", "block"]).difference.agg(["sum", "count"])
    sums = grouped["sum"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
    counts = grouped["count"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
    draws = (weights @ sums.T / (weights @ counts.T)).mean(axis=1)
    assert np.isfinite(draws).all()
    paired.append(
        dict(
            task=task,
            weather=weather,
            reference="weather_soaring",
            difference=frame.groupby("english_name").difference.mean().mean(),
            low=np.quantile(draws, 0.025),
            high=np.quantile(draws, 0.975),
        )
    )
pd.DataFrame(paired).to_csv(OUT / "comparison_paired.csv", index=False)
season = pd.concat(
    [
        pd.read_csv(ROOT / "season_errors.csv"),
        pd.read_csv(PREVIOUS / "season_errors.csv").query("method == 'weather_soaring'"),
    ],
    ignore_index=True,
)
season.groupby(["english_name", "method"]).absolute_relative_error.mean().unstack("method").to_csv(
    OUT / "comparison_season_species.csv"
)
season.groupby(["english_name", "method"]).absolute_relative_error.mean().groupby(
    "method"
).mean().to_csv(OUT / "comparison_season_scores.csv")
season = season.pivot(
    index=["english_name", "year"], columns="method", values="absolute_relative_error"
)
blocks = sorted(season.index.get_level_values("year").unique())
matrix = (
    (season.weather_lift - season.weather_soaring)
    .unstack("year")
    .reindex(columns=blocks)
    .to_numpy()
)
assert np.isfinite(matrix).all()
weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
draws = (weights @ matrix.T / len(blocks)).mean(axis=1)
pd.DataFrame(
    [
        dict(
            reference="weather_soaring",
            difference=matrix.mean(),
            low=np.quantile(draws, 0.025),
            high=np.quantile(draws, 0.975),
        )
    ]
).to_csv(OUT / "comparison_season_paired.csv", index=False)
print(pd.read_csv(OUT / "comparison_scores.csv").to_string(index=False))
print(pd.read_csv(OUT / "comparison_season_scores.csv").to_string(index=False))
print(pd.DataFrame(paired).to_string(index=False))
