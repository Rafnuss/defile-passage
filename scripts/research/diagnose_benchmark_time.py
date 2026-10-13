"""Refit benchmark time-component ablations on the ten-core historical seven-day task."""

import argparse
from dataclasses import replace
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from compare_production import interval_slots, training_profile

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T


def reduced_design(variant, years, doy_range, *, drop, design_function):
    """Remove named time blocks, retaining and reindexing the other original penalties."""
    full = design_function(variant, years, doy_range)
    if not drop:
        return full
    blocks, keep, offset = [], [], 0
    for block in full.blocks:
        if block.name in drop:
            continue
        indices = np.arange(block.columns.start, block.columns.stop)
        keep.extend(indices)
        blocks.append(replace(block, columns=slice(offset, offset + len(indices))))
        offset += len(indices)
    return T.Design(
        variant, full.years, full.doy_range, blocks, lambda y, d: full.X(y, d)[:, keep]
    )


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/history-diagnosis/benchmark-time"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
parser.add_argument("--keys", nargs="+")
args = parser.parse_args()
manifest = pd.read_csv(ROOT / "logs/historical-counts/design/manifest.csv").query("fold == 2")
manifest = manifest.iloc[args.shard[0] :: args.shard[1]]
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
original_design = T.design
for context in manifest.itertuples():
    source = ROOT / "logs/historical-counts/design"
    obs = pd.read_csv(
        source / f"{context.key}_observations.csv", parse_dates=["date"], low_memory=False
    )
    parts = pd.read_csv(
        source / f"{context.key}_components.csv", parse_dates=["date"], low_memory=False
    )
    parts["start"], parts["end"] = pd.to_datetime(parts.start, utc=True), pd.to_datetime(
        parts.end, utc=True
    )
    timed = obs[~obs.hidden & obs.source.eq("recent") & obs.resolution.eq("hour")]
    sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
        timed[["observation_id", "count"]], on="observation_id", validate="one_to_one"
    )
    sample["exposure_hours"] = sample.fraction
    profile = training_profile(sample)
    slots = interval_slots(parts)
    parts["c"] = (
        slots * profile[np.clip(parts.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
    ).sum(axis=1)
    obs = obs.join(parts.groupby("observation_id").c.sum(), on="observation_id")
    train = obs[~obs.hidden]
    daily = train.groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
    years = np.arange(obs.year.min(), obs.year.max() + 1)
    calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    calendar = calendar[E.in_window(pd.Series(calendar)).to_numpy()]
    frame = (
        pd.DataFrame(dict(date=calendar, year=calendar.year, doy=T.season_day(calendar)))
        .join(daily, on="date")
        .fillna({"y": 0, "c": 0})
    )
    low = frame.c.lt(T.MIN_COVERAGE)
    frame["extra"] = frame.y.where(low, 0)
    frame.loc[low, ["y", "c"]] = 0
    target = obs[obs.hidden].groupby("date").agg(count=("count", "sum"), c=("c", "sum"))
    reference = pd.read_csv(
        ROOT / f"logs/historical-counts/fits/{context.key}/assessment.csv", parse_dates=["date"]
    ).set_index("date")
    output = []
    for arm, drop in [
        ("full", []),
        ("no_shift", ["shift"]),
        ("no_episode", ["episode"]),
        ("neither", ["shift", "episode"]),
    ]:
        T.design = partial(reduced_design, drop=drop, design_function=original_design)
        fit = T.fit("gam", frame, years, (int(parts.doy.min()), int(parts.doy.max())))
        T.design = original_design
        mu = np.exp(
            T.eta_draws(
                fit,
                frame.year,
                frame.doy,
                fit.draws(500, np.random.default_rng(20261012 + context.fold)),
            )
        )
        rate = pd.Series(
            ((fit.theta + frame.y.to_numpy()) / (fit.theta / mu + frame.c.to_numpy())).mean(
                axis=0
            ),
            index=frame.date,
        )
        sample = target.copy()
        sample["predicted"] = sample.c * rate.reindex(sample.index)
        if arm == "full":
            print(
                "Full comparison max difference:",
                abs(sample.predicted - reference.original_episode).max(),
                flush=True,
            )
            assert np.allclose(sample.predicted, reference.original_episode, atol=1e-6, rtol=1e-6)
        sample["weather"] = reference.weather
        sample["english_name"], sample["year"], sample["arm"] = (
            context.english_name,
            sample.index.year,
            arm,
        )
        sample["theta"], sample["coefficients"] = fit.theta, fit.design.n_columns
        output.append(sample.reset_index())
        print(context.key, arm, "completed", flush=True)
    folder = OUT / context.key
    folder.mkdir(parents=True, exist_ok=True)
    pd.concat(output).to_csv(folder / "assessment.csv", index=False)
