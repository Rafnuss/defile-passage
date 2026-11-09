"""Training-selected daily-passage amplitude on one frozen core context."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from daily_passage_model import ar1_penalty, fit_daily_passage, scoring_information, scoring_step
from scipy.linalg import solve
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

from defile_passage.export import WINDOW

OUT = Path("logs/daily-passage")
SOURCE = Path("logs/history-episode")
SD_GRID = [0, 0.25, 0.5, 1]
EDF_PROBES = 32
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--key", required=True)
parser.add_argument("--out", type=Path, default=OUT)
parser.add_argument("--variance-power", type=float, choices=[1, 1.5], default=1.5)
parser.add_argument("--numerical-only", action="store_true")
args = parser.parse_args()
OUT = args.out
power = args.variance_power
key = args.key
folder = OUT / "fits" / key
folder.mkdir(parents=True, exist_ok=True)
started = perf_counter()
obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
parts = pd.read_csv(SOURCE / f"design/{key}_components.csv", low_memory=False)
index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
hidden = obs.hidden.to_numpy()
training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
dates = pd.to_datetime(obs.loc[~hidden, "date"])
weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
ridge = np.diag(
    (
        terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
        | terms.str.startswith("factor(year)")
    ).astype(float)
)
saved = np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")
penalty = float(saved["smoothing"]) * P + ridge
calendar = pd.DatetimeIndex(
    [
        date
        for year in sorted(parts.year.unique())
        for date in pd.date_range(pd.Timestamp(year, *WINDOW[0]), pd.Timestamp(year, *WINDOW[1]))
    ]
)
years = pd.factorize(calendar.year)[0]
day = calendar.get_indexer(pd.to_datetime(parts.date))
assert day.min() >= 0
n, p = len(calendar), X.shape[1]
C = csr_matrix((np.ones(n), (years, np.arange(n))))
Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), n))
scores, checks, histories = [], [], []
selection_started = perf_counter()
if not args.numerical_only:
    for sd in SD_GRID:
        held = np.zeros(len(y))
        for fold in range(3):
            mask = weeks % 3 == fold
            fit_started = perf_counter()
            if sd == 0:
                fit, objective = fit_rate(X, training[~mask], y[~mask], penalty, power)
                daily = np.zeros(n)
                history = []
            else:
                fit, objective, history = fit_daily_passage(
                    X,
                    training[~mask],
                    y[~mask],
                    penalty,
                    day,
                    years,
                    sd,
                    variance_power=power,
                    curvature_scale=power == 1,
                )
                daily = fit.x[p:]
            seconds = perf_counter() - fit_started
            np.savez(
                folder / f"cv_sd{sd}_fold{fold}.npz",
                coefficients=fit.x[:p],
                daily=daily,
                sd=sd,
                variance_power=power,
            )
            checks.append(
                dict(
                    sd=sd,
                    fold=fold,
                    gradient=abs(fit.jac).max(),
                    derivative_error=check_rate_gradient(objective, fit.x),
                    center_error=abs(C @ daily).max(),
                    iterations=fit.nit,
                    success=fit.success,
                    message=fit.message,
                    seconds=seconds,
                )
            )
            histories.extend(dict(sd=sd, fold=fold, **row) for row in history)
            held[mask] = training[mask] @ np.exp(X @ fit.x[:p] + daily[day])
        daily_score = (
            pd.DataFrame(dict(date=dates.to_numpy(), count=y, predicted=held))
            .groupby("date")[["count", "predicted"]]
            .sum()
        )
        daily_score.assign(sd=sd).to_csv(folder / f"cv_daily_sd{sd}.csv", index=True)
        scores.append(
            dict(sd=sd, daily_mae=abs(daily_score["count"] - daily_score.predicted).mean())
        )
    checks = pd.DataFrame(checks)
    checks.to_csv(folder / "cv_checks.csv", index=False)
    pd.DataFrame(scores).to_csv(folder / "amplitude_scores.csv", index=False)
    pd.DataFrame(histories).to_csv(folder / "cv_history.csv", index=False)
    selection_seconds = perf_counter() - selection_started
    assert checks.gradient.lt(0.001).all() and checks.derivative_error.lt(0.001).all(), key
    assert checks.center_error.lt(1e-9).all(), key
    selected = min(scores, key=lambda row: row["daily_mae"])["sd"]
else:
    selected = 0.5
    selection_seconds = 0
diagnostics, rates = [], {}
for method, sd in [("weather_mean", 0), ("weather_daily", selected)]:
    fit_started = perf_counter()
    if sd == 0:
        fit, objective = fit_rate(X, training, y, penalty, power)
        daily, history = np.zeros(n), []
    else:
        fit, objective, history = fit_daily_passage(
            X,
            training,
            y,
            penalty,
            day,
            years,
            sd,
            variance_power=power,
            curvature_scale=power == 1,
        )
        daily = fit.x[p:]
    seconds = perf_counter() - fit_started
    rates[method] = np.exp(X @ fit.x[:p] + daily[day])
    if method == "weather_mean" and power == 1.5:
        assert np.max(abs(np.exp(X @ (fit.x - saved["coefficients"])) - 1)) < 1e-5
        old_loss = objective(saved["coefficients"])[0]
        assert abs(fit.fun - old_loss) / max(1, abs(old_loss)) < 1e-7
    if sd == 0:
        J = training.multiply(rates[method]) @ X
        information = J.T @ ((training @ rates[method])[:, None] ** -power * J)
        effective_df = np.trace(solve(information + penalty, information, assume_a="pos"))
        edf_se = 0
    else:
        bb, cross, uu, shared, daily_J, weights = scoring_information(
            X, training, penalty, ar1_penalty(years, sd), Z, rates[method], power
        )
        probes = np.random.default_rng(20261012).choice([-1.0, 1.0], size=(p + n, EDF_PROBES))
        mapped = shared @ probes[:p] + daily_J @ probes[p:]
        rhs = np.vstack(
            [shared.T @ (weights[:, None] * mapped), daily_J.T @ (weights[:, None] * mapped)]
        )
        influence, _ = scoring_step(bb, cross, uu, C, rhs)
        traces = (probes * influence).sum(axis=0)
        effective_df, edf_se = traces.mean(), traces.std(ddof=1) / np.sqrt(EDF_PROBES)
    diagnostics.append(
        dict(
            key=key,
            method=method,
            sd=sd,
            variance_power=power,
            retained_count_error=float((training @ rates[method]).sum() - y.sum()),
            coefficients=len(fit.x),
            seconds=seconds + (selection_seconds if method == "weather_daily" else 0),
            final_seconds=seconds,
            selection_seconds=selection_seconds if method == "weather_daily" else 0,
            gradient=abs(fit.jac).max(),
            derivative_error=check_rate_gradient(objective, fit.x),
            center_error=abs(C @ daily).max(),
            iterations=fit.nit,
            success=fit.success,
            message=fit.message,
            effective_df=effective_df,
            effective_df_mc_se=edf_se,
            whole_context_seconds=perf_counter() - started,
        )
    )
    np.savez(
        folder / f"{method}_fit.npz",
        coefficients=fit.x[:p],
        daily=daily,
        sd=sd,
        variance_power=power,
    )
    pd.DataFrame(history).to_csv(folder / f"{method}_history.csv", index=False)
    pd.DataFrame(dict(date=calendar, daily_deviation=daily)).to_csv(
        folder / f"{method}_daily_values.csv", index=False
    )
diagnostics = pd.DataFrame(diagnostics)
diagnostics.to_csv(folder / "diagnostics.csv", index=False)
assert diagnostics.gradient.lt(0.001).all() and diagnostics.derivative_error.lt(0.001).all(), key
assert diagnostics.center_error.lt(1e-9).all(), key
if args.numerical_only:
    print(key, "numerical pilot completed", flush=True)
    raise SystemExit(0)
target = pd.read_csv(SOURCE / f"fits/{key}/assessment.csv").drop(columns="weather_episode")
for method in rates:
    prediction = (
        obs[hidden][["date"]]
        .assign(predicted=A[hidden] @ rates[method])
        .groupby("date")
        .predicted.sum()
        .reindex(target.date)
        .to_numpy()
    )
    if method == "weather_mean" and power == 1.5:
        assert np.allclose(prediction, target.weather_mean, atol=1e-5, rtol=1e-5)
    target[method] = prediction
target.to_csv(folder / "assessment.csv", index=False)
print(key, "completed", flush=True)
