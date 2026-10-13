"""Gamma integration and joint predictive sampling for the shared activity model."""

import numpy as np
from adaptive_daily_integration import adaptive_hurdle_rules, flat_hurdle_state_draws
from scipy.linalg import eigh_tridiagonal
from scipy.special import gammaln, logsumexp
from scipy.stats import nbinom


def gamma_quadrature(shape, order):
    """Normalized Gauss-Laguerre weights without overflowing Gamma(shape)."""
    index = np.arange(1, order)
    nodes, vectors = eigh_tridiagonal(
        (2 * np.arange(order) + shape) / shape,
        np.sqrt(index * (index + shape - 1)) / shape,
        lapack_driver="stev",
    )
    return nodes, 2 * np.log(np.abs(vectors[0]))


def joint_count_draws(
    training,
    testing,
    X,
    Xt,
    alpha,
    beta,
    covariance,
    shape,
    kappa,
    nodes,
    log_weights,
    draws,
    rng,
    adaptive=False,
    adaptive_order=31,
):
    """Share coefficients globally and a conditioned activity state within each day."""
    coefficients = rng.multivariate_normal(np.r_[alpha, beta], covariance, draws).T
    n = X.shape[1]
    train_h = training.exposure_hours.to_numpy()[:, None] * np.exp(
        np.clip(X @ coefficients[:n], -30, 30)
    )
    train_mu = training.exposure_hours.to_numpy()[:, None] * np.exp(
        np.clip(X @ coefficients[n:], -30, 30)
    )
    test_h = testing.exposure_hours.to_numpy()[:, None] * np.exp(
        np.clip(Xt @ coefficients[:n], -30, 30)
    )
    test_mu = testing.exposure_hours.to_numpy()[:, None] * np.exp(
        np.clip(Xt @ coefficients[n:], -30, 30)
    )
    count_draws = np.zeros((len(testing), draws))
    density = np.empty_like(count_draws)
    expected = np.empty_like(count_draws)
    probability_draws = np.empty_like(count_draws)
    for date in testing.date.unique():
        retained = np.flatnonzero(training.date.to_numpy() == date)
        hidden = np.flatnonzero(testing.date.to_numpy() == date)
        if len(retained) and not training["count"].to_numpy()[retained].any():
            state = rng.gamma(shape, 1 / (shape + train_h[retained].sum(axis=0)))
        elif len(retained):
            if adaptive:
                draw_nodes, draw_weights, mode_sd = adaptive_hurdle_rules(
                    shape,
                    training["count"].to_numpy()[retained],
                    train_h[retained],
                    train_mu[retained],
                    kappa * training.exposure_hours.to_numpy()[retained],
                    adaptive_order,
                    return_sd=True,
                )
                y = training["count"].to_numpy()[retained, None, None]
                size = kappa * training.exposure_hours.to_numpy()[retained, None, None]
                gh = train_h[retained, None, :] * draw_nodes[None, :, :]
                gm = train_mu[retained, None, :] * draw_nodes[None, :, :]
                log_p0 = -size * np.log1p(gm / size)
                log_nb = (
                    gammaln(y + size)
                    - gammaln(size)
                    - gammaln(y + 1)
                    + size * np.log(size)
                    + y * np.log(gm)
                    - (y + size) * np.log(size + gm)
                )
                likelihood = np.where(
                    y == 0, -gh, np.log(-np.expm1(-gh)) + log_nb - np.log(-np.expm1(log_p0))
                )
                weights = draw_weights + likelihood.sum(axis=0)
                posterior = np.exp(weights - logsumexp(weights, axis=0))
                uniforms = rng.uniform(size=draws)
                selected = (posterior.cumsum(axis=0) < uniforms).sum(axis=0)
                state = draw_nodes[selected, np.arange(draws)]
                flat = np.flatnonzero(mode_sd > 3)
                for start in range(0, len(flat), 32):
                    indices = flat[start : start + 32]
                    state[indices] = flat_hurdle_state_draws(
                        shape,
                        training["count"].to_numpy()[retained],
                        train_h[retained][:, indices],
                        train_mu[retained][:, indices],
                        kappa * training.exposure_hours.to_numpy()[retained],
                        uniforms[indices],
                    )
            if not adaptive:
                y = training["count"].to_numpy()[retained, None, None]
                size = kappa * training.exposure_hours.to_numpy()[retained, None, None]
                gh = train_h[retained, None, :] * nodes[None, :, None]
                gm = train_mu[retained, None, :] * nodes[None, :, None]
                log_p0 = -size * np.log1p(gm / size)
                log_nb = (
                    gammaln(y + size)
                    - gammaln(size)
                    - gammaln(y + 1)
                    + size * np.log(size)
                    + y * np.log(gm)
                    - (y + size) * np.log(size + gm)
                )
                rows = np.where(
                    y == 0, -gh, np.log(-np.expm1(-gh)) + log_nb - np.log(-np.expm1(log_p0))
                )
                weights = log_weights[:, None] + rows.sum(axis=0)
                posterior = np.exp(weights - logsumexp(weights, axis=0))
                selected = (posterior.cumsum(axis=0) < rng.uniform(size=draws)).sum(axis=0)
                state = nodes[selected]
        else:
            state = rng.gamma(shape, 1 / shape, draws)
        gh = test_h[hidden] * state
        gm = test_mu[hidden] * state
        size = kappa * testing.exposure_hours.to_numpy()[hidden, None]
        log_p0 = -size * np.log1p(gm / size)
        nonzero = -np.expm1(log_p0)
        probability = -np.expm1(-gh)
        probability_draws[hidden] = probability
        expected[hidden] = probability * gm / nonzero
        active = rng.uniform(size=gm.shape) < probability
        size_full = np.broadcast_to(size, gm.shape)
        quantile = np.minimum(
            np.exp(log_p0[active]) + nonzero[active] * rng.uniform(size=active.sum()),
            np.nextafter(1.0, 0.0),
        )
        sampled = np.zeros_like(gm)
        sampled[active] = np.maximum(
            1,
            nbinom.ppf(
                quantile, size_full[active], size_full[active] / (size_full[active] + gm[active])
            ),
        )
        count_draws[hidden] = sampled
        y = testing["count"].to_numpy()[hidden, None]
        log_nb = (
            gammaln(y + size)
            - gammaln(size)
            - gammaln(y + 1)
            + size * np.log(size)
            + y * np.log(gm)
            - (y + size) * np.log(size + gm)
        )
        density[hidden] = np.where(y == 0, -gh, np.log(probability) + log_nb - np.log(nonzero))
    return (
        count_draws,
        expected,
        logsumexp(density, axis=1) - np.log(draws),
        probability_draws.mean(axis=1),
    )
