"""One bounded original-plus-rain comparison on the frozen forty assessment contexts."""

import argparse
from functools import partial
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from compare_production import interval_slots, training_profile
from original_rain_model import ORIGINAL_DESIGN, RAIN_TERMS, rain_design

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T

SOURCE = Path("logs/history-episode")
OUT = Path("logs/original-rain")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
(OUT / "design").mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
if args.shard[0] == 0:
    manifest.to_csv(OUT / "design/manifest.csv", index=False)
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
weather = pd.read_csv("logs/era5-features/weather.csv").set_index("slot_start").rain_mm
weather.index = pd.to_datetime(weather.index, utc=True)

for context in manifest.itertuples():
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    obs = pd.read_csv(
        SOURCE / f"design/{key}_observations.csv", parse_dates=["date"], low_memory=False
    )
    parts = pd.read_csv(
        SOURCE / f"design/{key}_components.csv", parse_dates=["date"], low_memory=False
    )
    # Match the saved original pipeline: recent references use recent training only.
    if context.task == "recent":
        obs = obs[obs.source.eq("recent")].copy()
        parts = parts[parts.observation_id.isin(obs.observation_id)].copy()
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
    del slots
    obs = obs.join(parts.groupby("observation_id").c.sum(), on="observation_id")
    daily = obs[~obs.hidden].groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
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
    # Integrate ERA5 over the full solar-day profile, including unobserved days.
    noon = calendar + pd.Timedelta(hours=12)
    utc_noon = noon.tz_localize(E.TIMEZONE).tz_convert("UTC").tz_localize(None)
    zone = (noon - utc_noon) / pd.Timedelta(hours=1)
    shift = E.solar_shift(frame.date).to_numpy() - np.asarray(zone)
    midpoint = (np.arange(E.SLOTS) + 0.5) / E.STEPS_PER_HOUR
    times = calendar.to_numpy()[:, None] + pd.to_timedelta(
        (shift[:, None] + midpoint).ravel(), unit="h"
    ).to_numpy().reshape(len(calendar), E.SLOTS)
    times = pd.to_datetime(times.ravel(), utc=True).floor("h")
    rain = weather.reindex(times).to_numpy().reshape(len(calendar), E.SLOTS)
    weights = profile[np.clip(frame.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
    rain = np.column_stack(
        [
            (weights * np.log1p(rain)).sum(axis=1),
            (weights * np.maximum(np.log1p(rain) - np.log(2), 0)).sum(axis=1),
        ]
    )
    assert np.isfinite(rain).all() and np.allclose(weights.sum(axis=1), 1)
    scale = rain[frame.c.gt(0)].std(axis=0, ddof=1)
    rain = pd.DataFrame(
        rain / scale, columns=RAIN_TERMS, index=pd.MultiIndex.from_frame(frame[["year", "doy"]])
    )
    rain.to_csv(folder / "daily_rain.csv")
    pd.Series(scale, index=RAIN_TERMS).to_csv(folder / "rain_scales.csv")
    target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(columns="weather_episode")
    hidden_c = obs[obs.hidden].groupby("date").c.sum()
    diagnostics = []
    for method in ["original_replay", "original_rain"]:
        T.design = (
            ORIGINAL_DESIGN if method == "original_replay" else partial(rain_design, rain=rain)
        )
        started = perf_counter()
        try:
            fit = T.fit("gam", frame, years, (int(parts.doy.min()), int(parts.doy.max())))
        finally:
            T.design = ORIGINAL_DESIGN
        seconds = perf_counter() - started
        draw = fit.draws(500, np.random.default_rng(20261012 + context.fold))
        mu = np.exp(T.eta_draws(fit, frame.year, frame.doy, draw))
        rate = pd.Series(
            ((fit.theta + frame.y.to_numpy()) / (fit.theta / mu + frame.c.to_numpy())).mean(
                axis=0
            ),
            index=frame.date,
        )
        prediction = hidden_c * rate.reindex(hidden_c.index)
        target[method] = prediction.reindex(pd.to_datetime(target.date)).to_numpy()
        # Independently check the posterior mode score, retaining all raw hyperparameters.
        X = fit.design.X(frame.loc[frame.c.gt(0), "year"], frame.loc[frame.c.gt(0), "doy"])
        mean = frame.loc[frame.c.gt(0), "c"].to_numpy() * np.exp(X @ fit.beta)
        score = X.T @ (
            fit.theta * (frame.loc[frame.c.gt(0), "y"].to_numpy() - mean) / (fit.theta + mean)
        )
        prior = fit.design.prior(fit.hyper)
        score -= prior @ fit.beta
        correction = fit.H.solve(score)
        diagnostics.append(
            dict(
                key=key,
                method=method,
                seconds=seconds,
                score=abs(score).max(),
                mode_step=abs(correction).max(),
                eta_step=abs(X @ correction).max(),
                theta=fit.theta,
                coefficients=len(fit.beta),
            )
        )
        np.savez(folder / f"{method}.npz", coefficients=fit.beta, draws=draw)
        pd.Series(fit.hyper).to_csv(folder / f"{method}_hyper.csv")
    target.to_csv(folder / "assessment.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(folder / "diagnostics.csv", index=False)
    print(key, "completed", flush=True)
