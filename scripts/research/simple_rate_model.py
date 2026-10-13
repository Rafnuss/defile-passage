"""Small count-rate fit with direct interval-mean aggregation."""

import numpy as np
from scipy.optimize import minimize
from scipy.special import xlogy


def fit_rate(X, aggregation, counts, penalty, variance_power=1, weights=1, solver="BFGS"):
    """Fit an interval mean without allocating its observed count to hours."""
    initial = np.zeros(X.shape[1])
    initial[0] = np.log(counts.sum() / aggregation.sum())

    def objective(coefficients):
        rate = np.exp(X @ coefficients)
        mean = aggregation @ rate
        if variance_power == 1:
            loss = (weights * (mean - counts + xlogy(counts, counts / mean))).sum()
        else:
            loss = (weights * 2 * (np.sqrt(mean) - np.sqrt(counts)) ** 2 / np.sqrt(mean)).sum()
        loss += coefficients @ penalty @ coefficients / 2
        score = 1 - counts / mean if variance_power == 1 else (mean - counts) / mean**1.5
        gradient = X.T @ (rate * (aggregation.T @ (weights * score))) + penalty @ coefficients
        return loss, gradient

    def curvature(coefficients):
        rate = np.exp(X @ coefficients)
        mean = aggregation @ rate
        derivative = aggregation @ (rate[:, None] * X)
        score = 1 - counts / mean if variance_power == 1 else (mean - counts) / mean**1.5
        residual = rate * (aggregation.T @ (weights * score))
        weight = (
            weights
            * ((1 - variance_power) * mean + variance_power * counts)
            / mean ** (variance_power + 1)
        )
        return (
            derivative.T @ (weight[:, None] * derivative) + X.T @ (residual[:, None] * X) + penalty
        )

    result = minimize(
        objective,
        initial,
        jac=True,
        **({"hess": curvature} if solver != "BFGS" else {}),
        method=solver,
        options={"gtol": 1e-5, "maxiter": 200 if solver == "BFGS" else 100},
    )
    # Numerical checks always evaluate the returned coefficients.
    result.fun, result.jac = objective(result.x)
    return result, objective


def check_rate_gradient(objective, coefficients):
    """Remove central-difference truncation error for high-count species."""
    directions = np.random.default_rng(20261012).normal(size=(8, len(coefficients)))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    analytic = directions @ objective(coefficients)[1]
    estimates = []
    for step in [1e-3, 5e-4]:
        estimates.append(
            np.array(
                [
                    (objective(coefficients + step * d)[0] - objective(coefficients - step * d)[0])
                    / (2 * step)
                    for d in directions
                ]
            )
        )
    numerical = (4 * estimates[1] - estimates[0]) / 3
    return np.max(np.abs(analytic - numerical) / np.maximum(1, np.abs(numerical)))
