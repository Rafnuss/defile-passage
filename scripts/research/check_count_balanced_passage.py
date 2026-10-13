"""Independent numerical checks for the count-balanced daily criterion."""

import numpy as np
from daily_passage_model import (
    ar1_penalty,
    center_daily,
    daily_objective,
    directional_curvature,
    fit_daily_passage,
    scoring_information,
    scoring_step,
)
from scipy.linalg import solve
from scipy.optimize import minimize
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

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
counts, P = np.array([0, 8, 30, 5, 18]), np.diag([0, 1])
Q = ar1_penalty(years)
C = csr_matrix((np.ones(len(years)), (years, np.arange(len(years)))))
Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), len(years)))
point = np.r_[2.0, -0.3, center_daily(np.linspace(-0.4, 0.8, len(years)), years)]
rate = np.exp(X @ point[:2] + point[2:][day])
for power in [1, 1.5]:
    objective = daily_objective(X, A, counts, P, Q, day, years, power)
    assert check_rate_gradient(objective, point) < 1e-6
    base, base_objective = fit_rate(X, A, counts, P, power)
    zero_state = np.r_[base.x, np.zeros(len(years))]
    assert np.allclose(objective(zero_state)[0], base_objective(base.x)[0], atol=1e-12)
    assert np.allclose(objective(zero_state)[1][:2], base_objective(base.x)[1], atol=1e-12)
    bb, cross, uu, _, _, _ = scoring_information(X, A, P, Q, Z, rate, power)
    gradient = objective(point)[1]
    direction, _ = scoring_step(bb, cross, uu, C, gradient[:, None])
    direction = direction[:, 0]
    H = np.block([[bb, cross], [cross.T, uu.toarray()]])
    D = np.column_stack([np.zeros((2, 2)), C.toarray()])
    dense = solve(np.block([[H, D.T], [D, np.zeros((2, 2))]]), np.r_[gradient, [0, 0]])[
        : len(point)
    ]
    assert np.allclose(direction, dense, atol=1e-10, rtol=1e-10)
    direction /= np.linalg.norm(direction)
    curvature = directional_curvature(X, A, counts, P, Q, day, rate, direction, power)
    finite = (
        direction
        @ (objective(point + 1e-4 * direction)[1] - objective(point - 1e-4 * direction)[1])
        / (2e-4)
    )
    assert np.isclose(curvature, finite, atol=1e-7, rtol=1e-7)
    fit, objective, history = fit_daily_passage(
        X, A, counts, P, day, years, variance_power=power, curvature_scale=True
    )
    assert abs(fit.jac).max() < 0.001 and check_rate_gradient(objective, fit.x) < 0.001
    assert np.allclose(C @ fit.x[2:], 0, atol=1e-12)
    assert np.diff([row["loss"] for row in history]).max() <= 0
    independent = minimize(
        objective, point, jac=True, method="BFGS", options={"gtol": 1e-8, "maxiter": 200}
    )
    assert abs(fit.fun - independent.fun) < 1e-7
    if power == 1:
        fitted = A @ np.exp(X @ fit.x[:2] + fit.x[2:][day])
        assert abs(fitted.sum() - counts.sum()) < 0.001
        # Intercept curvature and gradient must reduce to raw count balance.
        intercept = np.r_[1.0, np.zeros(len(point) - 1)]
        assert np.isclose(objective(point)[1][0], (A @ rate - counts).sum())
        assert np.isclose(
            directional_curvature(X, A, counts, P, Q, day, rate, intercept, power),
            (A @ rate).sum(),
        )

# The historical default path keeps identical coefficients and loss.
legacy, _, _ = fit_daily_passage(X, A, counts, P, day, years)
explicit, _, _ = fit_daily_passage(
    X, A, counts, P, day, years, variance_power=1.5, curvature_scale=False
)
assert np.array_equal(legacy.x, explicit.x) and legacy.fun == explicit.fun
print(
    "Both gradients/curvatures, dense constrained solve, independent optimum, count balance and legacy replay pass."
)
