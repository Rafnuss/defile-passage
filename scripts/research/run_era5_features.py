"""Test antecedent rain and radiation/cloud separately with the retained interval-rate model."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.linalg import block_diag
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

SOURCE = Path("logs/history-episode")
FEATURES = {
    "rain_history": ["log_previous_rain", "dry_previous_rain"],
    "soaring": ["radiation_200", "low_cloud_fraction"],
    "lift": ["log_boundary_layer_km", "upward_heat_100"],
}
SMOOTHING_GRID = [0.1, 1, 10]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
parser.add_argument("--root", type=Path, default=Path("logs/era5-features"))
parser.add_argument("--variants", nargs="+", choices=FEATURES, default=["rain_history", "soaring"])
args = parser.parse_args()
OUT = args.root
FEATURES = {name: FEATURES[name] for name in args.variants}
weather = pd.read_csv(OUT / "weather.csv").set_index("slot_start")
weather.index = pd.to_datetime(weather.index, utc=True)
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
for variant in FEATURES:
    (OUT / variant / "design").mkdir(parents=True, exist_ok=True)
    if args.shard[0] == 0:
        manifest.to_csv(OUT / variant / "design/manifest.csv", index=False)
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]

for context in manifest.itertuples():
    key = context.key
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
    parts = pd.read_csv(SOURCE / f"design/{key}_components.csv", low_memory=False)
    hourly = weather.reindex(pd.to_datetime(parts.slot_start, utc=True))
    assert np.isfinite(hourly.to_numpy()).all()
    assert np.allclose(hourly.rain_mm, parts.rain_mm, atol=1e-6)
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
    dates = pd.to_datetime(obs.loc[~hidden, "date"])
    weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
    base_X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
    base_P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
    ridge = np.diag(
        (
            terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
            | terms.str.startswith("factor(year)")
        ).astype(float)
    )
    assert base_X.shape[1] == 51
    saved = np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")

    for variant, features in FEATURES.items():
        folder = OUT / variant / "fits" / key
        folder.mkdir(parents=True, exist_ok=True)
        target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(columns="weather_episode")
        diagnostics = []
        for method in ["weather_mean", f"weather_{variant}"]:
            started = perf_counter()
            X = base_X if method == "weather_mean" else np.column_stack([base_X, hourly[features]])
            P = (
                base_P
                if method == "weather_mean"
                else block_diag(base_P, np.zeros((len(features), len(features))))
            )
            R = ridge if method == "weather_mean" else block_diag(ridge, np.eye(len(features)))
            fit_terms = (
                terms
                if method == "weather_mean"
                else pd.concat([terms, pd.Series(features)], ignore_index=True)
            )
            smoothing = float(saved["smoothing"])
            if method != "weather_mean":
                scores, checks = [], []
                for strength in SMOOTHING_GRID:
                    held = np.zeros(len(y))
                    for fold in range(3):
                        mask = weeks % 3 == fold
                        fit, objective = fit_rate(
                            X, training[~mask], y[~mask], strength * P + R, 1.5
                        )
                        checks.append(
                            dict(
                                smoothing=strength,
                                fold=fold,
                                gradient=abs(fit.jac).max(),
                                derivative_error=check_rate_gradient(objective, fit.x),
                                iterations=fit.nit,
                                success=fit.success,
                                message=fit.message,
                            )
                        )
                        np.savez(folder / f"inner_{strength}_{fold}.npz", coefficients=fit.x)
                        held[mask] = training[mask] @ np.exp(X @ fit.x)
                    pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held)).to_csv(
                        folder / f"inner_predictions_{strength}.csv", index=False
                    )
                    daily = (
                        pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held))
                        .groupby("date")[["count", "predicted"]]
                        .sum()
                    )
                    scores.append(
                        dict(
                            smoothing=strength,
                            daily_mae=abs(daily["count"] - daily.predicted).mean(),
                        )
                    )
                pd.DataFrame(scores).to_csv(folder / "smoothing_scores.csv", index=False)
                checks = pd.DataFrame(checks)
                checks.to_csv(folder / "cv_checks.csv", index=False)
                assert (
                    checks.gradient.lt(0.001).all() and checks.derivative_error.lt(0.001).all()
                ), (key, variant)
                smoothing = min(scores, key=lambda row: row["daily_mae"])["smoothing"]
            final_started = perf_counter()
            fit, objective = fit_rate(X, training, y, smoothing * P + R, 1.5)
            final_seconds = perf_counter() - final_started
            gradient, derivative = abs(fit.jac).max(), check_rate_gradient(objective, fit.x)
            np.savez(folder / f"{method}_fit.npz", coefficients=fit.x, smoothing=smoothing)
            pd.DataFrame(dict(term=fit_terms, coefficient=fit.x)).to_csv(
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
                    success=fit.success,
                    message=fit.message,
                )
            )
            pd.DataFrame(diagnostics).to_csv(folder / "diagnostics.csv", index=False)
            assert gradient < 0.001 and derivative < 0.001, (key, method, gradient, derivative)
            prediction = (
                obs[hidden][["date"]]
                .assign(predicted=A[hidden] @ np.exp(X @ fit.x))
                .groupby("date")
                .predicted.sum()
                .reindex(target.date)
                .to_numpy()
            )
            if method == "weather_mean":
                assert np.max(abs(np.exp(base_X @ (fit.x - saved["coefficients"])) - 1)) < 1e-5
                assert (
                    abs(fit.fun - objective(saved["coefficients"])[0]) / max(1, abs(fit.fun))
                    < 1e-7
                )
                assert np.allclose(prediction, target.weather_mean, atol=1e-5, rtol=1e-5)
            target[method] = prediction
        target.to_csv(folder / "assessment.csv", index=False)
    print(key, "completed", flush=True)
