"""Test independent season/clock penalties in the unchanged small weather mean."""

import argparse
from itertools import product
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/separate-smoothing")
SOURCE = Path("logs/history-episode")
SMOOTHING_GRID = [0.1, 1, 10]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
(OUT / "design").mkdir(parents=True, exist_ok=True)
if args.shard[0] == 0:
    manifest.to_csv(OUT / "design/manifest.csv", index=False)
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
for context in manifest.itertuples():
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
    parts = pd.read_csv(
        SOURCE / f"design/{key}_components.csv", usecols=["observation_id", "fraction"]
    )
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
    dates = pd.to_datetime(obs.loc[~hidden, "date"])
    weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
    X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
    season = terms.str.startswith("season_").to_numpy()
    clock = terms.str.fullmatch(r"(?:sin|cos)[123]").to_numpy()
    season_penalty = P * np.outer(season, season)
    clock_penalty = P * np.outer(clock, clock)
    assert season.sum() == 7 and clock.sum() == 6 and X.shape[1] == 51
    assert np.array_equal(season_penalty + clock_penalty, P)
    ridge = np.diag(
        (
            terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
            | terms.str.startswith("factor(year)")
        ).astype(float)
    )
    saved = np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")
    scores, checks = [], []
    started = perf_counter()
    for season_strength, clock_strength in product(SMOOTHING_GRID, repeat=2):
        penalty = season_strength * season_penalty + clock_strength * clock_penalty + ridge
        held = np.zeros(len(y))
        for fold in range(3):
            mask = weeks % 3 == fold
            fit, objective = fit_rate(X, training[~mask], y[~mask], penalty, 1.5)
            checks.append(
                dict(
                    season_smoothing=season_strength,
                    clock_smoothing=clock_strength,
                    fold=fold,
                    gradient=abs(fit.jac).max(),
                    derivative_error=check_rate_gradient(objective, fit.x),
                    iterations=fit.nit,
                    success=fit.success,
                    message=fit.message,
                )
            )
            held[mask] = training[mask] @ np.exp(X @ fit.x)
        daily = (
            pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held))
            .groupby("date")[["count", "predicted"]]
            .sum()
        )
        scores.append(
            dict(
                season_smoothing=season_strength,
                clock_smoothing=clock_strength,
                daily_mae=abs(daily["count"] - daily.predicted).mean(),
            )
        )
    checks = pd.DataFrame(checks)
    checks.to_csv(folder / "cv_checks.csv", index=False)
    pd.DataFrame(scores).to_csv(folder / "smoothing_scores.csv", index=False)
    assert checks.gradient.lt(0.001).all() and checks.derivative_error.lt(0.001).all(), key
    selected = min(scores, key=lambda row: row["daily_mae"])
    cv_seconds = perf_counter() - started
    target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(columns="weather_episode")
    diagnostics = []
    for method, season_strength, clock_strength in [
        ("weather_mean", float(saved["smoothing"]), float(saved["smoothing"])),
        ("weather_separate", selected["season_smoothing"], selected["clock_smoothing"]),
    ]:
        penalty = season_strength * season_penalty + clock_strength * clock_penalty + ridge
        final_started = perf_counter()
        fit, objective = fit_rate(X, training, y, penalty, 1.5)
        final_seconds = perf_counter() - final_started
        gradient, derivative = abs(fit.jac).max(), check_rate_gradient(objective, fit.x)
        assert gradient < 0.001 and derivative < 0.001, (key, method, gradient, derivative)
        rate_difference = np.max(abs(np.exp(X @ (fit.x - saved["coefficients"])) - 1))
        if method == "weather_mean":
            assert rate_difference < 1e-5, (key, rate_difference)
            old_loss = objective(saved["coefficients"])[0]
            assert abs(fit.fun - old_loss) / max(1, abs(old_loss)) < 1e-7
        prediction = (
            obs[hidden][["date"]]
            .assign(predicted=A[hidden] @ np.exp(X @ fit.x))
            .groupby("date")
            .predicted.sum()
            .reindex(target.date)
            .to_numpy()
        )
        if method == "weather_mean":
            assert np.allclose(prediction, target.weather_mean, atol=1e-5, rtol=1e-5)
        target[method] = prediction
        np.savez(
            folder / f"{method}_fit.npz",
            coefficients=fit.x,
            season_smoothing=season_strength,
            clock_smoothing=clock_strength,
        )
        pd.DataFrame(dict(term=terms, coefficient=fit.x)).to_csv(
            folder / f"{method}_coefficients.csv", index=False
        )
        diagnostics.append(
            dict(
                key=key,
                method=method,
                coefficients=len(fit.x),
                seconds=final_seconds + (cv_seconds if method == "weather_separate" else 0),
                final_seconds=final_seconds,
                gradient=gradient,
                derivative_error=derivative,
                season_smoothing=season_strength,
                clock_smoothing=clock_strength,
                iterations=fit.nit,
                success=fit.success,
                message=fit.message,
            )
        )
    target.to_csv(folder / "assessment.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(folder / "diagnostics.csv", index=False)
    print(key, "completed", flush=True)
