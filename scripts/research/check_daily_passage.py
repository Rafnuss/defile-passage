"""Independent synthetic checks before the daily-passage numerical pilot."""

from pathlib import Path

import numpy as np
import pandas as pd
from daily_passage_model import (
    CORRELATION_DAYS,
    DAILY_SD,
    ar1_penalty,
    center_daily,
    daily_objective,
    fit_daily_passage,
    scoring_information,
    scoring_step,
)
from scipy.linalg import solve
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/daily-passage-pilot")
OUT.mkdir(parents=True, exist_ok=True)
years = np.repeat([0, 1], 6)
day = np.array([0, 0, 1, 4, 5, 6, 7, 10, 11])
X = np.column_stack([np.ones(len(day)), np.linspace(-1, 1, len(day))])
A = csr_matrix(
    [
        [0.5, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0.5, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0.75, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0.5, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 1],
    ]
)
counts = np.array([0, 8, 30, 5, 18])
P = np.diag([0, 1])
Q = ar1_penalty(years)
C = csr_matrix((np.ones(len(years)), (years, np.arange(len(years)))))
Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), len(years)))
point = np.r_[2.0, -0.3, center_daily(np.linspace(-0.4, 0.8, len(years)), years)]
objective = daily_objective(X, A, counts, P, Q, day, years)
assert check_rate_gradient(objective, point) < 1e-6
rate = np.exp(X @ point[:2] + point[2:][day])
assert np.allclose(
    A @ rate,
    [
        0.5 * rate[0],
        rate[1] + 0.5 * rate[2],
        rate[3] + 0.75 * rate[4],
        0.5 * rate[5] + rate[6],
        rate[7] + rate[8],
    ],
)
rho = np.exp(-1 / CORRELATION_DAYS)
manual = 0
for year in [0, 1]:
    u = point[2:][years == year]
    manual += (u[0] ** 2 + ((u[1:] - rho * u[:-1]) ** 2).sum() / (1 - rho**2)) / (
        2 * DAILY_SD**2
    )
assert np.allclose(point[2:] @ Q @ point[2:] / 2, manual)
assert Q[5, 6] == 0 and np.allclose(C @ point[2:], 0)
assert np.array_equal(Q.toarray(), ar1_penalty(years, DAILY_SD).toarray())
for sd in [0.25, 1]:
    precision = ar1_penalty(years, sd)
    assert np.allclose(point[2:] @ precision @ point[2:] / 2, manual * (DAILY_SD / sd) ** 2)
    alternative = daily_objective(X, A, counts, P, precision, day, years)
    assert check_rate_gradient(alternative, point) < 1e-6

# The sparse constrained step must match an independent dense KKT solve.
bb, cross, uu, _, _, _ = scoring_information(X, A, P, Q, Z, rate)
gradient = objective(point)[1]
step, _ = scoring_step(bb, cross, uu, C, gradient[:, None])
H = np.block([[bb, cross], [cross.T, uu.toarray()]])
D = np.column_stack([np.zeros((2, 2)), C.toarray()])
KKT = np.block([[H, D.T], [D, np.zeros((2, 2))]])
dense = solve(KKT, np.r_[gradient, np.zeros(2)])[: len(point)]
assert np.allclose(step[:, 0], dense, atol=1e-10, rtol=1e-10)
assert np.allclose(C @ step[2:], 0, atol=1e-12)

# Verify the multi-right-hand-side influence calculation used for effective DF.
data_information = H - np.block([[P, np.zeros((2, 12))], [np.zeros((12, 2)), Q.toarray()]])
influence, _ = scoring_step(bb, cross, uu, C, data_information)
dense_influence = solve(KKT, np.vstack([data_information, np.zeros((2, len(point)))]))
assert np.allclose(influence, dense_influence[: len(point)], atol=1e-10, rtol=1e-10)
assert 0 < np.trace(influence) < len(counts)

# Removing deviations exactly recovers the unchanged rate objective.
base, base_objective = fit_rate(X, A, counts, P, 1.5)
no_daily = np.r_[base.x, np.zeros(len(years))]
assert np.allclose(objective(no_daily)[0], base_objective(base.x)[0], atol=1e-12)
assert np.allclose(objective(no_daily)[1][:2], base_objective(base.x)[1], atol=1e-12)
fit, objective, history = fit_daily_passage(X, A, counts, P, day, years)
assert abs(fit.jac).max() < 0.001 and check_rate_gradient(objective, fit.x) < 0.001
assert np.allclose(C @ fit.x[2:], 0, atol=1e-12)
assert np.diff([row["loss"] for row in history]).max() <= 0
pd.DataFrame(history).to_csv(OUT / "synthetic_history.csv", index=False)
print("Synthetic checks pass: derivatives, zeros, interval sums, cross-date counts, empty runs,")
print("year reset/centering, AR(1) endpoint, dense KKT agreement and no-deviation baseline.")
