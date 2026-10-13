"""Compare actual historical interval holdouts with the original architecture."""

import argparse
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from compare_production import interval_slots, training_profile

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=ROOT / "logs/historical-counts")
parser.add_argument("--keys", nargs="+")
parser.add_argument("--shard", nargs=2, type=int)
args = parser.parse_args()
OUT = args.root
manifest = pd.read_csv(OUT / "design/manifest.csv")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
if args.shard:
    names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
    manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
profiles = {}
for context in manifest.itertuples():
    started = perf_counter()
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "run.log").open("w") as log:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/research/fit_simple_rate.py",
                "--input",
                str(OUT / "design"),
                "--out",
                str(folder),
                "--variant",
                "year_weather",
                "--keys",
                key,
                "--select-smoothing",
                "--variance-power",
                "1.5",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    if result.returncode:
        print(key, "FAILED mean fit", flush=True)
        continue
    obs = pd.read_csv(OUT / f"design/{key}_observations.csv", parse_dates=["date"])
    parts = pd.read_csv(OUT / f"design/{key}_components.csv", parse_dates=["date"])
    parts["start"], parts["end"] = pd.to_datetime(parts.start, utc=True), pd.to_datetime(
        parts.end, utc=True
    )
    if context.english_name not in profiles:
        timed = obs[~obs.hidden & obs.source.eq("recent") & obs.resolution.eq("hour")]
        sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
            timed[["observation_id", "count"]], on="observation_id", validate="one_to_one"
        )
        sample["exposure_hours"] = sample.fraction
        profiles[context.english_name] = training_profile(sample)
    profile = profiles[context.english_name]
    slots = interval_slots(parts)
    parts["c"] = (
        slots * profile[np.clip(parts.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
    ).sum(axis=1)
    parts["rain_hours"] = parts.rain_mm * parts.fraction
    coverage = parts.groupby("observation_id").agg(
        c=("c", "sum"), rain_hours=("rain_hours", "sum")
    )
    obs = obs.join(coverage, on="observation_id")
    train = obs[~obs.hidden]
    daily = train.groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
    years = np.arange(obs.year.min(), obs.year.max() + 1)
    calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    calendar = calendar[E.in_window(pd.Series(calendar)).to_numpy()]
    frame = (
        pd.DataFrame({"date": calendar, "year": calendar.year, "doy": T.season_day(calendar)})
        .join(daily, on="date")
        .fillna({"y": 0, "c": 0})
    )
    low = frame.c.lt(T.MIN_COVERAGE)
    frame["extra"] = frame.y.where(low, 0)
    frame.loc[low, ["y", "c"]] = 0
    fit = T.fit("gam", frame, years, (int(parts.doy.min()), int(parts.doy.max())))
    mu = np.exp(
        T.eta_draws(
            fit,
            frame.year,
            frame.doy,
            fit.draws(500, np.random.default_rng(20261012 + context.fold)),
        )
    )
    rate = pd.Series(
        ((fit.theta + frame.y.to_numpy()) / (fit.theta / mu + frame.c.to_numpy())).mean(axis=0),
        index=frame.date,
    )
    target = (
        obs[obs.hidden]
        .groupby("date")
        .agg(
            count=("count", "sum"),
            c=("c", "sum"),
            hours=("exposure_hours", "sum"),
            rain_hours=("rain_hours", "sum"),
        )
    )
    target["original_episode"] = target.c * rate.reindex(target.index)
    prediction = pd.read_csv(folder / "predictions.csv", parse_dates=["date"])
    target["weather_mean"] = prediction.groupby("date").predicted.sum().reindex(target.index)
    target["retained_count"] = train.groupby("date")["count"].sum().reindex(target.index).fillna(0)
    target["retained_hours"] = (
        train.groupby("date").exposure_hours.sum().reindex(target.index).fillna(0)
    )
    target["weather"] = np.where(target.rain_hours / target.hours >= 0.1, "wet", "dry")
    target["year"] = target.index.year
    target["english_name"], target["fold"] = context.english_name, context.fold
    target.reset_index().to_csv(folder / "assessment.csv", index=False)
    season = (
        obs[obs.source.eq("historical")]
        .groupby("year")
        .agg(
            observed_truth=("count", "sum"),
            truth_hours=("exposure_hours", "sum"),
            truth_dates=("date", "nunique"),
        )
    )
    for method in ["weather_mean", "original_episode"]:
        error = (target[method] - target["count"]).groupby(target.year).sum()
        season[method + "_bias"] = error.reindex(season.index).fillna(0)
        season[method + "_reconstructed"] = season.observed_truth + season[method + "_bias"]
    season["english_name"], season["fold"] = context.english_name, context.fold
    season.to_csv(folder / "season_totals.csv")
    print(key, "completed", round(perf_counter() - started, 2), flush=True)
