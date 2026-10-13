"""Test a richer shared season without adding episodes or changing weather/time terms."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/history-season")
SOURCE = Path("logs/history-episode")
SMOOTHING_GRID = [0.1, 1, 10]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
manifest = pd.read_csv(OUT / "design/manifest.csv")
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
for context in manifest.itertuples():
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv")
    parts = pd.read_csv(SOURCE / f"design/{key}_components.csv")
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
    dates = pd.to_datetime(obs.loc[~hidden, "date"])
    weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
    target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(columns="weather_episode")
    saved = np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")
    diagnostics = []
    for method, directory, suffix in [
        ("weather_mean", SOURCE / "design", "_year_weather"),
        ("weather_season", OUT / "design", ""),
    ]:
        started = perf_counter()
        X = np.loadtxt(directory / f"{key}{suffix}_X.csv", delimiter=",")
        P = np.loadtxt(directory / f"{key}{suffix}_penalty.csv", delimiter=",")
        terms = pd.read_csv(directory / f"{key}{suffix}_terms.csv").term
        ridge = np.diag(
            (
                terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
                | terms.str.startswith("factor(year)")
            ).astype(float)
        )
        smoothing = float(saved["smoothing"])
        if method == "weather_season":
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
                        solver="trust-exact",
                    )
                    assert abs(fit.jac).max() < 0.001, (key, strength, fold, fit.message)
                    held[mask] = training[mask] @ np.exp(X @ fit.x)
                daily = (
                    pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held))
                    .groupby("date")[["count", "predicted"]]
                    .sum()
                )
                scores.append(
                    dict(
                        smoothing=strength, daily_mae=abs(daily["count"] - daily.predicted).mean()
                    )
                )
            pd.DataFrame(scores).to_csv(folder / "smoothing_scores.csv", index=False)
            smoothing = min(scores, key=lambda row: row["daily_mae"])["smoothing"]
        final_started = perf_counter()
        fit, objective = fit_rate(X, training, y, smoothing * P + ridge, 1.5, solver="trust-exact")
        final_seconds = perf_counter() - final_started
        gradient, derivative = abs(fit.jac).max(), check_rate_gradient(objective, fit.x)
        assert gradient < 0.001 and derivative < 0.001, (key, method, gradient, derivative)
        if method == "weather_mean":
            assert np.allclose(fit.x, saved["coefficients"], atol=1e-7, rtol=1e-7)
        prediction = (
            obs[hidden][["date"]]
            .assign(predicted=A[hidden] @ np.exp(X @ fit.x))
            .groupby("date")
            .predicted.sum()
        )
        if method == "weather_mean":
            assert np.allclose(
                prediction.reindex(target.date), target.weather_mean, atol=1e-7, rtol=1e-7
            )
        target[method] = prediction.reindex(target.date).to_numpy()
        np.savez(folder / f"{method}_fit.npz", coefficients=fit.x, smoothing=smoothing)
        pd.DataFrame(dict(term=terms, coefficient=fit.x)).to_csv(
            folder / f"{method}_coefficients.csv", index=False
        )
        diagnostics.append(
            dict(
                key=key,
                method=method,
                coefficients=len(fit.x),
                seconds=perf_counter() - started,
                final_seconds=final_seconds,
                gradient=gradient,
                derivative_error=derivative,
                smoothing=smoothing,
                iterations=fit.nit,
            )
        )
    target.to_csv(folder / "assessment.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(folder / "diagnostics.csv", index=False)
    print(key, "completed", flush=True)
