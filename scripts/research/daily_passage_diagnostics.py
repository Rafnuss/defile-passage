"""Fixed-point observed curvature and conditional daily curvature diagnostics."""

import numpy as np
from scipy.linalg import solve
from scipy.sparse import diags


def observed_information(X, aggregation, counts, penalty, precision, day_design, rate):
    """Exact objective curvature before projecting onto yearly-centered values."""
    mean = aggregation @ rate
    shared = aggregation.multiply(rate) @ X
    daily = aggregation.multiply(rate) @ day_design
    weights = (-0.5 * mean + 1.5 * counts) / mean**2.5
    residual = rate * (aggregation.T @ ((mean - counts) / mean**1.5))
    bb = shared.T @ (weights[:, None] * shared) + X.T @ (residual[:, None] * X) + penalty
    cross = (daily.T @ (weights[:, None] * shared)).T + (day_design.T @ (residual[:, None] * X)).T
    uu = (
        daily.T @ daily.multiply(weights[:, None])
        + precision
        + diags(np.asarray(day_design.T @ residual).ravel())
    ).tocsc()
    return bb, cross, uu


def conditional_daily_variance(information, years):
    """Centered local Gaussian proxy with shared coefficients and SD fixed."""
    variance = np.zeros(len(years))
    for year in np.unique(years):
        index = np.flatnonzero(years == year)
        covariance = solve(
            information[index][:, index].toarray(), np.eye(len(index)), assume_a="pos"
        )
        row_sum = covariance.sum(axis=1)
        variance[index] = np.diag(covariance) - row_sum**2 / row_sum.sum()
    return variance
