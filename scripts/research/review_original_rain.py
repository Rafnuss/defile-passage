"""Review the complete original-plus-rain batch once, without target-based tuning."""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage import trend as T

OUT = Path("logs/original-rain")
manifest = pd.read_csv(OUT / "design/manifest.csv")
assert len(manifest) == 40 and manifest.english_name.nunique() == 10
wide = pd.concat(
    [pd.read_csv(OUT / f"fits/{key}/assessment.csv").assign(key=key) for key in manifest.key],
    ignore_index=True,
)
original = pd.read_csv("logs/history-episode/predictions.csv").query(
    "method == 'original_episode'"
)
wide = wide.merge(
    original[["date", "task", "english_name", "fold", "count", "predicted"]],
    on=["date", "task", "english_name", "fold"],
    validate="one_to_one",
    suffixes=("", "_reference"),
).rename(columns={"predicted": "original_episode"})
assert np.array_equal(wide["count"], wide.count_reference)
replay = wide.original_replay - wide.original_episode
pd.DataFrame(dict(key=wide.key, date=wide.date, difference=replay)).to_csv(
    OUT / "baseline_replay.csv", index=False
)
historical = wide.task.eq("historical")
pd.Series(
    {
        "historical_strict_replay": np.allclose(
            wide.loc[historical, "original_replay"],
            wide.loc[historical, "original_episode"],
            atol=1e-6,
            rtol=1e-6,
        ),
        "historical_max_difference": abs(replay[historical]).max(),
        "recent_max_difference": abs(replay[~historical]).max(),
    }
).to_csv(OUT / "baseline_replay_status.csv")
wide["saved_original"] = wide.original_episode
wide["original_episode"] = wide.original_replay
soaring = pd.read_csv("logs/era5-features/soaring/predictions.csv").query(
    "method == 'weather_soaring'"
)
wide = wide.merge(
    soaring[["date", "task", "english_name", "fold", "predicted"]].rename(
        columns={"predicted": "weather_soaring"}
    ),
    on=["date", "task", "english_name", "fold"],
    validate="one_to_one",
)
methods = ["original_episode", "original_rain", "weather_soaring"]
assert np.isfinite(wide[methods].to_numpy()).all()
long = wide.melt(
    id_vars=["key", "date", "task", "english_name", "fold", "count", "weather", "year"],
    value_vars=methods,
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
species.to_csv(OUT / "species_scores.csv")
scores = species.groupby(["task", "weather"])[methods].mean()
scores.to_csv(OUT / "group_scores.csv")
summary.groupby(
    ["task", "era", "weather", "english_name", "method"], observed=True
).absolute_error.mean().groupby(
    ["task", "era", "weather", "method"], observed=True
).mean().unstack(
    "method"
).to_csv(
    OUT / "era_scores.csv"
)
summary.groupby(
    ["task", "year", "weather", "english_name", "method"]
).absolute_error.mean().groupby(["task", "year", "weather", "method"]).mean().unstack(
    "method"
).to_csv(
    OUT / "year_scores.csv"
)
summary.groupby(["task", "weather", "method"]).agg(
    truth=("count", "sum"), predicted=("predicted", "sum"), bias=("error", "sum")
).to_csv(OUT / "total_bias.csv")

# Joint year/week bootstrap retains shared weather across species.
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
    for reference in ["original_episode", "weather_soaring"]:
        frame = frame.assign(
            difference=abs(frame.original_rain - frame["count"])
            - abs(frame[reference] - frame["count"])
        )
        grouped = frame.groupby(["english_name", "block"]).difference.agg(["sum", "count"])
        sums = grouped["sum"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        counts = grouped["count"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        draws = ((weights @ sums.T) / (weights @ counts.T)).mean(axis=1)
        paired.append(
            dict(
                task=task,
                weather=weather,
                reference=reference,
                difference=frame.groupby("english_name").difference.mean().mean(),
                low=np.quantile(draws, 0.025),
                high=np.quantile(draws, 0.975),
            )
        )
pd.DataFrame(paired).to_csv(OUT / "paired_scores.csv", index=False)

# Convert both standardized coefficients back to their common log-rain units.
rain_coefficients = []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    fit = np.load(folder / "original_rain.npz")
    rain = pd.read_csv(folder / "daily_rain.csv")
    groups = rain.year.nunique()
    split = len(fit["coefficients"]) - groups * (T.GAM_EPISODE_K - 1) - 2
    coefficient = fit["coefficients"][split : split + 2]
    scale = pd.read_csv(folder / "rain_scales.csv", index_col=0).iloc[:, 0].to_numpy()
    rain_coefficients.append(
        dict(
            key=context.key,
            task=context.task,
            english_name=context.english_name,
            log_rain=coefficient[0],
            rain_hinge=coefficient[1],
            slope_above_1mm=(coefficient / scale).sum(),
        )
    )
pd.DataFrame(rain_coefficients).to_csv(OUT / "rain_coefficients.csv", index=False)


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
    season.groupby(["english_name", "method"]).absolute_relative_error.mean().unstack("method")
)
season_scores.to_csv(OUT / "season_species_scores.csv")
season_scores.mean().to_csv(OUT / "season_scores.csv")
diagnostics = pd.concat(
    [pd.read_csv(OUT / f"fits/{key}/diagnostics.csv") for key in manifest.key], ignore_index=True
)
diagnostics.to_csv(OUT / "diagnostics.csv", index=False)
assert np.isfinite(diagnostics[["score", "mode_step", "eta_step"]].to_numpy()).all()
print(scores.to_string())
print("Season errors:", season_scores.mean().to_string())
print(
    "Species improving versus original:",
    (species.original_rain < species.original_episode)
    .groupby(["task", "weather"])
    .sum()
    .to_string(),
)
print("Median fit seconds:", diagnostics.groupby("method").seconds.median().to_string())
print("Maximum posterior score:", diagnostics.groupby("method").score.max().to_string())
print("Maximum original replay difference:", abs(replay).max())
print(pd.DataFrame(paired).to_string(index=False))
