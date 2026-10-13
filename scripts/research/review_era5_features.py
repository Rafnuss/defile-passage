"""Review the completed ERA5 screen, including dry recovery and multi-day totals."""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path("logs/era5-features"))
parser.add_argument("--variants", nargs="+", default=["rain_history", "soaring"])
args = parser.parse_args()
OUT = args.root
SOURCE = Path("logs/history-episode")
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
weather = pd.read_csv(OUT / "weather.csv").set_index("slot_start")
weather.index = pd.to_datetime(weather.index, utc=True)
conditions = []
for context in manifest.itertuples():
    parts = pd.read_csv(SOURCE / f"design/{context.key}_components.csv", low_memory=False)
    parts = parts[parts.hidden].copy()
    hourly = weather.reindex(pd.to_datetime(parts.slot_start, utc=True))
    parts["previous_rain"] = hourly.rain_previous_24h_mm.to_numpy() * parts.fraction
    parts["radiation"] = hourly.radiation_w_m2.to_numpy() * parts.fraction
    parts["cloud"] = hourly.low_cloud_fraction.to_numpy() * parts.fraction
    daily = parts.groupby("date")[["previous_rain", "radiation", "cloud", "fraction"]].sum()
    daily[["previous_rain", "radiation", "cloud"]] = daily[
        ["previous_rain", "radiation", "cloud"]
    ].div(daily.fraction, axis=0)
    daily["key"] = context.key
    conditions.append(daily.reset_index())
conditions = pd.concat(conditions, ignore_index=True)
conditions.to_csv(OUT / "target_weather.csv", index=False)

for variant in args.variants:
    root = OUT / variant
    candidate = f"weather_{variant}"
    # Reuse the frozen core-species, original-model and total-error assessment.
    with (root / "review.log").open("w") as log:
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/research/review_history_season.py",
                "--root",
                str(root),
                "--candidate",
                candidate,
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    frames, checks = [], []
    for context in manifest.itertuples():
        folder = root / "fits" / context.key
        frames.append(pd.read_csv(folder / "assessment.csv").assign(key=context.key))
        checks.append(pd.read_csv(folder / "cv_checks.csv").assign(key=context.key))
    checks = pd.concat(checks, ignore_index=True)
    assert (
        len(checks) == 360
        and checks.gradient.lt(0.001).all()
        and checks.derivative_error.lt(0.001).all()
    )
    checks.to_csv(root / "cv_checks.csv", index=False)
    wide = pd.concat(frames, ignore_index=True).merge(
        conditions, on=["key", "date"], validate="one_to_one"
    )
    wide["condition"] = np.where(
        wide.weather.eq("wet"),
        "wet",
        np.where(wide.previous_rain.ge(1), "dry_after_rain", "dry_background"),
    )
    wide["rain_band"] = pd.cut(
        wide.rain_hours / wide.hours,
        [-np.inf, 0.1, 1, 3, np.inf],
        labels=["dry", "0.1–1", "1–3", "≥3"],
        right=False,
    )
    wide.to_csv(root / "weather_assessment.csv", index=False)
    original = pd.read_csv(root / "predictions.csv").query("method == 'original_episode'")
    wide = wide.merge(
        original[["date", "task", "english_name", "fold", "predicted"]],
        on=["date", "task", "english_name", "fold"],
        validate="one_to_one",
    ).rename(columns={"predicted": "original_episode"})
    methods = ["weather_mean", candidate, "original_episode"]
    long = wide.melt(
        id_vars=["date", "task", "english_name", "fold", "condition", "rain_band", "count"],
        value_vars=methods,
        var_name="method",
        value_name="predicted",
    )
    long["error"] = long.predicted - long["count"]
    long["absolute_error"] = abs(long.error)
    long.groupby(["task", "condition", "english_name", "method"]).agg(
        days=("date", "size"),
        mae=("absolute_error", "mean"),
        bias=("error", "sum"),
        truth=("count", "sum"),
        predicted=("predicted", "sum"),
    ).to_csv(root / "condition_species.csv")
    condition = (
        long.groupby(["task", "condition", "english_name", "method"])
        .absolute_error.mean()
        .groupby(["task", "condition", "method"])
        .mean()
        .unstack("method")
    )
    condition.to_csv(root / "condition_scores.csv")
    long.groupby(["task", "rain_band", "english_name", "method"], observed=True).agg(
        days=("date", "size"),
        mae=("absolute_error", "mean"),
        truth=("count", "sum"),
        predicted=("predicted", "sum"),
    ).to_csv(root / "rain_band_species.csv")
    species = pd.read_csv(root / "species_scores.csv")
    sensitivity = []
    for (task, band), frame in species.groupby(["task", "weather"]):
        reduced = frame[~frame.english_name.eq("European Honey Buzzard")]
        sensitivity.append(
            dict(
                task=task,
                weather=band,
                improving_species=int(frame[candidate].lt(frame.weather_mean).sum()),
                species=len(frame),
                mean_species_relative_change=(frame[candidate] / frame.weather_mean - 1).mean(),
                without_honey_buzzard_change=reduced[candidate].mean()
                / reduced.weather_mean.mean()
                - 1,
            )
        )
    pd.DataFrame(sensitivity).to_csv(root / "species_sensitivity.csv", index=False)
    long["week"] = (pd.to_datetime(long.date) - pd.Timestamp("1970-01-05")).dt.days // 7
    weekly = long.groupby(["task", "english_name", "fold", "week", "method"])[
        ["count", "predicted"]
    ].sum()
    weekly["absolute_error"] = abs(weekly.predicted - weekly["count"])
    weekly.to_csv(root / "weekly_totals.csv")
    weekly.groupby(["task", "english_name", "method"]).absolute_error.mean().groupby(
        ["task", "method"]
    ).mean().unstack("method").to_csv(root / "weekly_scores.csv")
    # Annual totals are paired across the same species and years.
    season = pd.read_csv(root / "season_errors.csv")
    season = season.pivot(
        index=["english_name", "year"], columns="method", values="absolute_relative_error"
    )
    blocks = sorted(season.index.get_level_values("year").unique())
    rng = np.random.default_rng(20261012)
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
    differences = []
    for reference in ["weather_mean", "original_episode"]:
        matrix = (
            (season[candidate] - season[reference])
            .unstack("year")
            .reindex(columns=blocks)
            .to_numpy()
        )
        assert np.isfinite(matrix).all()
        draws = (weights @ matrix.T / len(blocks)).mean(axis=1)
        differences.append(
            dict(
                reference=reference,
                difference=matrix.mean(),
                low=np.quantile(draws, 0.025),
                high=np.quantile(draws, 0.975),
            )
        )
    pd.DataFrame(differences).to_csv(root / "paired_season_scores.csv", index=False)
    print(variant)
    print(pd.read_csv(root / "group_scores.csv").to_string(index=False))
    print(condition.to_string())
    print(pd.read_csv(root / "season_scores.csv").to_string(index=False))
    print(pd.DataFrame(differences).to_string(index=False))
    print(pd.read_csv(root / "acceptance.csv").to_string(index=False))
