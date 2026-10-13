"""Posterior-centered integration of a shared Gamma state on its log scale."""

import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy.optimize import minimize_scalar
from scipy.special import gammaln, logsumexp


def hurdle_log_rows(nodes, counts, hazard, mean, size):
    gh = hazard[:, None] * nodes
    gm = mean[:, None] * nodes
    positive = counts > 0
    rows = -gh
    y, mu, r = counts[positive, None], gm[positive], size[positive, None]
    log_p0 = -r * np.log1p(mu / r)
    rows[positive] = (
        np.log(-np.expm1(-gh[positive]))
        + gammaln(y + r)
        - gammaln(r)
        - gammaln(y + 1)
        + r * np.log(r)
        + y * np.log(mu)
        - (y + r) * np.log(r + mu)
        - np.log(-np.expm1(log_p0))
    )
    return rows


def adaptive_gamma_rule(shape, log_likelihood, order=31):
    """Return nodes and prior integration weights centered on the daily posterior.

    The log-Gamma Jacobian is included. Weights are importance quadrature weights, not normalized
    prior probabilities; use logsumexp with the daily likelihood. Refined orders provide a separate
    integration accuracy check.
    """

    def log_joint(t):
        t = np.atleast_1d(t)
        return (
            shape * np.log(shape)
            - gammaln(shape)
            + shape * t
            - shape * np.exp(t)
            + log_likelihood(np.exp(t))
        )

    mode = minimize_scalar(
        lambda t: -float(log_joint(t)[0]),
        bounds=(-40, 15),
        method="bounded",
        options={"xatol": 1e-9},
    ).x
    step = 1e-3
    curvature = (
        -(log_joint(mode + step)[0] - 2 * log_joint(mode)[0] + log_joint(mode - step)[0])
        / step**2
    )
    sd = 1 / np.sqrt(curvature)
    abscissa, weights = hermgauss(order)
    t = mode + np.sqrt(2) * sd * abscissa
    prior = shape * np.log(shape) - gammaln(shape) + shape * t - shape * np.exp(t)
    log_weights = np.log(weights) + np.log(np.sqrt(2) * sd) + abscissa**2 + prior
    return np.exp(t), log_weights


def adaptive_hurdle_rule(shape, counts, hazard, mean, size, order=31):
    return adaptive_gamma_rule(
        shape, lambda nodes: hurdle_log_rows(nodes, counts, hazard, mean, size).sum(axis=0), order
    )


def adaptive_hurdle_log_probability(shape, counts, hazard, mean, size, order=31):
    if not np.any(counts):
        return -shape * np.log1p(np.sum(hazard) / shape)
    nodes, weights = adaptive_hurdle_rule(shape, counts, hazard, mean, size, order)
    return logsumexp(weights + hurdle_log_rows(nodes, counts, hazard, mean, size).sum(axis=0))


def adaptive_hurdle_rules(shape, counts, hazard, mean, size, order=31, return_sd=False):
    """Posterior-centered rules for many coefficient draws, using batched Newton steps."""
    y, r = counts[:, None], size[:, None]
    t = np.log((shape + counts.sum()) / (shape + hazard.sum(axis=0) + mean.sum(axis=0)))
    for _ in range(30):
        state = np.exp(t)
        gh, gm = hazard * state, mean * state
        positive = y > 0
        gate_score = np.where(
            positive, np.where(gh < 50, gh / np.expm1(np.minimum(gh, 50)), 0), -gh
        )
        gate_second = np.where(
            positive,
            np.where(gh < 1e-6, -gh / 2 + gh**2 / 6, gate_score * (1 - gh - gate_score)),
            -gh,
        )
        log0 = -r * np.log1p(gm / r)
        ratio = np.exp(log0) / (-np.expm1(log0))
        a = r * gm / (r + gm)
        mean_score = np.where(positive, y - gm * (y + r) / (r + gm) - ratio * a, 0)
        mean_second = np.where(
            positive,
            -gm * r * (y + r) / (r + gm) ** 2
            + ratio * (1 + ratio) * a**2
            - ratio * r**2 * gm / (r + gm) ** 2,
            0,
        )
        small_mean = gm / r < 1e-6
        mean_score = np.where(
            positive & small_mean, y - 1 - gm * (2 * y + r - 1) / (2 * r), mean_score
        )
        mean_second = np.where(positive & small_mean, -gm * (2 * y + r - 1) / (2 * r), mean_second)
        score = shape - shape * state + (gate_score + mean_score).sum(axis=0)
        curvature = shape * state - (gate_second + mean_second).sum(axis=0)
        step = np.clip(score / curvature, -3, 3)
        t += step
        if np.max(abs(step)) < 1e-8:
            break
    # Re-evaluate curvature at the final mode.
    state = np.exp(t)
    gh, gm = hazard * state, mean * state
    gate_score = np.where(positive, np.where(gh < 50, gh / np.expm1(np.minimum(gh, 50)), 0), -gh)
    gate_second = np.where(
        positive,
        np.where(gh < 1e-6, -gh / 2 + gh**2 / 6, gate_score * (1 - gh - gate_score)),
        -gh,
    )
    log0 = -r * np.log1p(gm / r)
    ratio = np.exp(log0) / (-np.expm1(log0))
    a = r * gm / (r + gm)
    mean_second = np.where(
        positive,
        -gm * r * (y + r) / (r + gm) ** 2
        + ratio * (1 + ratio) * a**2
        - ratio * r**2 * gm / (r + gm) ** 2,
        0,
    )
    mean_second = np.where(
        positive & (gm / r < 1e-6), -gm * (2 * y + r - 1) / (2 * r), mean_second
    )
    sd = 1 / np.sqrt(shape * state - (gate_second + mean_second).sum(axis=0))
    proposal_sd = np.minimum(sd, 3) if return_sd else sd
    abscissa, weights = hermgauss(order)
    log_nodes = t[None, :] + np.sqrt(2) * proposal_sd[None, :] * abscissa[:, None]
    prior = shape * np.log(shape) - gammaln(shape) + shape * log_nodes - shape * np.exp(log_nodes)
    log_weights = (
        np.log(weights)[:, None]
        + np.log(np.sqrt(2) * proposal_sd)[None, :]
        + abscissa[:, None] ** 2
        + prior
    )
    return (np.exp(log_nodes), log_weights, sd) if return_sd else (np.exp(log_nodes), log_weights)


def flat_hurdle_state_draws(shape, counts, hazard, mean, size, uniforms, step=0.05):
    """CDF inversion on log state for flat, asymmetric conditional posteriors."""
    from scipy.integrate import cumulative_trapezoid

    grid = np.arange(-100, 40 + step / 2, step)
    nodes = np.exp(grid)
    y, r = counts[:, None, None], size[:, None, None]
    gh, gm = hazard[:, None, :] * nodes[None, :, None], mean[:, None, :] * nodes[None, :, None]
    log0 = -r * np.log1p(gm / r)
    log_nb = (
        gammaln(y + r)
        - gammaln(r)
        - gammaln(y + 1)
        + r * np.log(r)
        + y * np.log(gm)
        - (y + r) * np.log(r + gm)
    )
    likelihood = np.where(
        y == 0, -gh, np.log(-np.expm1(-gh)) + log_nb - np.log(-np.expm1(log0))
    ).sum(axis=0)
    prior = shape * np.log(shape) - gammaln(shape) + shape * grid - shape * nodes
    joint = likelihood + prior[:, None]
    density = np.exp(joint - joint.max(axis=0))
    cdf = cumulative_trapezoid(density, grid, axis=0, initial=0)
    cdf /= cdf[-1]
    return np.array([np.exp(np.interp(u, cdf[:, i], grid)) for i, u in enumerate(uniforms)])
