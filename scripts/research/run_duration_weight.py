"""Compare unweighted, damped and square-root-duration fits on fixed contexts."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/duration-weight")
SOURCE = Path("logs/history-episode")
SMOOTHING_GRID = [0.1, 1, 10]
POWERS = [0.25, 0.5]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
parser.add_argument("--key")
parser.add_argument("--resume", action="store_true")
args = parser.parse_args()
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
for power in POWERS:
    directory = OUT / f"power-{power}/design"
    directory.mkdir(parents=True, exist_ok=True)
    # Only the first shard writes identical shared metadata.
    if args.shard[0] == 0:
        manifest.to_csv(directory / "manifest.csv", index=False)
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
if args.key:
    manifest = manifest[manifest.key.eq(args.key)]
for context in manifest.itertuples():
    key = context.key
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
    parts = pd.read_csv(
        SOURCE / f"design/{key}_components.csv", usecols=["observation_id", "fraction"]
    )
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
    duration = np.asarray(training.sum(axis=1)).ravel()
    assert np.allclose(duration, obs.loc[~hidden, "exposure_hours"])
    dates = pd.to_datetime(obs.loc[~hidden, "date"])
    weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
    original_target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(
        columns="weather_episode"
    )
    saved = np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")
    X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
    ridge = np.diag(
        (
            terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
            | terms.str.startswith("factor(year)")
        ).astype(float)
    )
    # Replay once, then share the identical baseline between both comparisons.
    started = perf_counter()
    base, objective = fit_rate(
        X, training, y, float(saved["smoothing"]) * P + ridge, 1.5, solver="trust-exact"
    )
    base_seconds = perf_counter() - started
    base_gradient, base_derivative = abs(base.jac).max(), check_rate_gradient(objective, base.x)
    assert base_gradient < 0.001 and base_derivative < 0.001
    assert np.allclose(base.x, saved["coefficients"], atol=1e-7, rtol=1e-7)
    base_prediction = (
        obs[hidden][["date"]]
        .assign(predicted=A[hidden] @ np.exp(X @ base.x))
        .groupby("date")
        .predicted.sum()
        .reindex(original_target.date)
        .to_numpy()
    )
    assert np.allclose(base_prediction, original_target.weather_mean, atol=1e-7, rtol=1e-7)
    for power in POWERS:
        started = perf_counter()
        folder = OUT / f"power-{power}/fits/{key}"
        folder.mkdir(parents=True, exist_ok=True)
        if args.resume and (folder / "diagnostics.csv").exists():
            continue
        weights = duration**power
        scores = []
        for strength in SMOOTHING_GRID:
            held = np.zeros(len(y))
            for fold in range(3):
                mask = weeks % 3 == fold
                fit, _ = fit_rate(
                    X,
                    training[~mask],
                    y[~mask],
                    strength * P + ridge,
                    1.5,
                    weights[~mask],
                    solver="trust-exact",
                )
                assert abs(fit.jac).max() < 0.001, (key, power, strength, fold, fit.message)
                held[mask] = training[mask] @ np.exp(X @ fit.x)
            daily = (
                pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held))
                .groupby("date")[["count", "predicted"]]
                .sum()
            )
            scores.append(
                dict(smoothing=strength, daily_mae=abs(daily["count"] - daily.predicted).mean())
            )
        pd.DataFrame(scores).to_csv(folder / "smoothing_scores.csv", index=False)
        smoothing = min(scores, key=lambda row: row["daily_mae"])["smoothing"]
        final_started = perf_counter()
        fit, objective = fit_rate(
            X, training, y, smoothing * P + ridge, 1.5, weights, solver="trust-exact"
        )
        final_seconds = perf_counter() - final_started
        gradient, derivative = abs(fit.jac).max(), check_rate_gradient(objective, fit.x)
        assert gradient < 0.001 and derivative < 0.001, (key, power, gradient, derivative)
        target = original_target.copy()
        target["weather_mean"] = base_prediction
        target["weather_weighted"] = (
            obs[hidden][["date"]]
            .assign(predicted=A[hidden] @ np.exp(X @ fit.x))
            .groupby("date")
            .predicted.sum()
            .reindex(target.date)
            .to_numpy()
        )
        target.to_csv(folder / "assessment.csv", index=False)
        np.savez(
            folder / "weather_weighted_fit.npz",
            coefficients=fit.x,
            smoothing=smoothing,
            duration_power=power,
        )
        pd.DataFrame(dict(term=terms, coefficient=fit.x)).to_csv(
            folder / "weather_weighted_coefficients.csv", index=False
        )
        pd.DataFrame(
            [
                dict(
                    key=key,
                    method="weather_mean",
                    coefficients=len(base.x),
                    seconds=base_seconds,
                    final_seconds=base_seconds,
                    gradient=base_gradient,
                    derivative_error=base_derivative,
                    smoothing=float(saved["smoothing"]),
                    iterations=base.nit,
                    duration_power=0,
                ),
                dict(
                    key=key,
                    method="weather_weighted",
                    coefficients=len(fit.x),
                    seconds=perf_counter() - started,
                    final_seconds=final_seconds,
                    gradient=gradient,
                    derivative_error=derivative,
                    smoothing=smoothing,
                    iterations=fit.nit,
                    duration_power=power,
                ),
            ]
        ).to_csv(folder / "diagnostics.csv", index=False)
    print(key, "completed", flush=True)
