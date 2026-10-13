"""One fixed numerical pilot context; never score hidden counts."""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from daily_passage_model import (
    ar1_penalty,
    daily_objective,
    fit_daily_passage,
    scoring_information,
    scoring_step,
)
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh
from simple_rate_model import check_rate_gradient, fit_rate

from defile_explore.export import WINDOW

OUT = Path("logs/daily-passage-pilot")
SOURCE = Path("logs/history-episode")
EDF_PROBES = 32
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--key", required=True)
args = parser.parse_args()
key = args.key
folder = OUT / "fits" / key
folder.mkdir(parents=True, exist_ok=True)
started = perf_counter()
obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
parts = pd.read_csv(SOURCE / f"design/{key}_components.csv")
index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
training = A[~obs.hidden.to_numpy()]
y = obs.loc[~obs.hidden, "count"].to_numpy()
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
Q = ar1_penalty(years)
C = csr_matrix((np.ones(n), (years, np.arange(n))))
Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), n))
base_started = perf_counter()
base, base_objective = fit_rate(X, training, y, penalty, 1.5)
base_seconds = perf_counter() - base_started
base_gradient = abs(base.jac).max()
base_derivative = check_rate_gradient(base_objective, base.x)
replay_rate_error = np.max(abs(np.exp(X @ (base.x - saved["coefficients"])) - 1))
old_loss = base_objective(saved["coefficients"])[0]
replay_loss_error = abs(base.fun - old_loss) / max(1, abs(old_loss))
objective = daily_objective(X, training, y, penalty, Q, day, years)
zero_state_loss = abs(objective(np.r_[base.x, np.zeros(n)])[0] - base.fun)
assert base_gradient < 0.001 and base_derivative < 0.001
assert replay_rate_error < 1e-5 and replay_loss_error < 1e-7 and zero_state_loss < 1e-7
fit_started = perf_counter()
fit, objective, history = fit_daily_passage(X, training, y, penalty, day, years)
seconds = perf_counter() - fit_started
pd.DataFrame(history).to_csv(folder / "history.csv", index=False)
np.savez(folder / "fit.npz", coefficients=fit.x[:p], daily=fit.x[p:])
gradient, derivative = abs(fit.jac).max(), check_rate_gradient(objective, fit.x)
center_error = abs(C @ fit.x[p:]).max()
rate = np.exp(X @ fit.x[:p] + fit.x[p:][day])
bb, cross, uu, shared, daily, weights = scoring_information(X, training, penalty, Q, Z, rate)

# Trace of constrained working-information influence, with Monte Carlo error.
rng = np.random.default_rng(20261012)
probes = rng.choice([-1.0, 1.0], size=(p + n, EDF_PROBES))
mapped = shared @ probes[:p] + daily @ probes[p:]
rhs = np.vstack([shared.T @ (weights[:, None] * mapped), daily.T @ (weights[:, None] * mapped)])
influence, schur = scoring_step(bb, cross, uu, C, rhs)
traces = (probes * influence).sum(axis=0)
schur_scale = np.sqrt(np.diag(schur))
schur_condition = np.linalg.cond(schur / np.outer(schur_scale, schur_scale))
daily_min = eigsh(uu, k=1, which="SA", tol=0.01, return_eigenvectors=False)[0]
daily_max = eigsh(uu, k=1, which="LA", tol=0.01, return_eigenvectors=False)[0]
diagnostics = dict(
    key=key,
    shared_coefficients=p,
    daily_values=n,
    free_daily_values=n - C.shape[0],
    observations=len(y),
    daily_information_nonzero=uu.nnz,
    gradient=gradient,
    derivative_error=derivative,
    center_error=center_error,
    iterations=fit.nit,
    success=fit.success,
    message=fit.message,
    objective_decreases=np.diff([row["loss"] for row in history]).max() <= 0,
    base_gradient=base_gradient,
    base_derivative=base_derivative,
    replay_rate_error=replay_rate_error,
    replay_loss_error=replay_loss_error,
    zero_state_loss=zero_state_loss,
    final_seconds=seconds,
    baseline_seconds=base_seconds,
    runtime_ratio=seconds / base_seconds,
    effective_df=traces.mean(),
    effective_df_mc_se=traces.std(ddof=1) / np.sqrt(EDF_PROBES),
    scaled_shared_schur_condition=schur_condition,
    conditional_daily_information_condition=daily_max / daily_min,
    whole_context_seconds=perf_counter() - started,
)
pd.DataFrame([diagnostics]).to_csv(folder / "diagnostics.csv", index=False)
pd.DataFrame(dict(date=calendar, daily_deviation=fit.x[p:])).to_csv(
    folder / "daily_values.csv", index=False
)
retained = parts[~parts.hidden].copy()
retained["rain_group"] = np.where(retained.rain_mm >= 0.1, "wet_hour", "dry_hour")
retained.groupby(["year", "rain_group"]).agg(
    observed_hours=("fraction", "sum"), rain_min=("rain_mm", "min"), rain_max=("rain_mm", "max")
).to_csv(folder / "weather_support.csv")
assert gradient < 0.001 and derivative < 0.001 and center_error < 1e-9, diagnostics
assert diagnostics["objective_decreases"]
print(key, "numerical context completed", flush=True)
