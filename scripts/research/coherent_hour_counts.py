"""Canonical-hour thinning and exact truncated convolution for coarse survey counts."""

import numpy as np
from scipy.optimize import brentq
from scipy.signal import fftconvolve
from scipy.special import gammaln, logsumexp


def thinned_hour_logpmf(counts, hazard, mean, size, fraction, state):
    """Log PMFs and log-rate scores, retaining full-hour NB size under thinning."""
    y, h, mu, r, q = np.broadcast_arrays(counts, state * hazard, state * mean, size, fraction)
    active = -np.expm1(-h)
    log0 = -r * np.log1p(mu / r)
    log0thin = -r * np.log1p(q * mu / r)
    nonzero = -np.expm1(log0)
    difference = np.exp(log0thin) * (-np.expm1(log0 - log0thin))
    with np.errstate(divide="ignore"):
        log_difference = log0thin + np.log(-np.expm1(log0 - log0thin))
        log_zero = np.logaddexp(-h, np.log(active) + log_difference - np.log(nonzero))
    positive = y > 0
    logp = np.empty_like(mu)
    logp[~positive] = log_zero[~positive]
    logp[positive] = (
        np.log(active[positive])
        + gammaln(y[positive] + r[positive])
        - gammaln(r[positive])
        - gammaln(y[positive] + 1)
        + r[positive] * np.log(r[positive])
        + y[positive] * np.log(q[positive] * mu[positive])
        - (y[positive] + r[positive]) * np.log(r[positive] + q[positive] * mu[positive])
        - np.log(nonzero[positive])
    )
    ratio = np.exp(log0) / nonzero
    a = r * mu / (r + mu)
    score_h = np.zeros_like(mu)
    score_m = np.zeros_like(mu)
    score_h[positive] = h[positive] / np.expm1(np.minimum(h[positive], 700))
    score_m[positive] = (
        y[positive]
        - q[positive]
        * mu[positive]
        * (y[positive] + r[positive])
        / (r[positive] + q[positive] * mu[positive])
        - ratio[positive] * a[positive]
    )
    partial_zero = ~positive & (q < 1)
    v = (-np.expm1(log0thin)) / nonzero
    score_h[partial_zero] = (
        -v[partial_zero] * h[partial_zero] * np.exp(-h[partial_zero] - logp[partial_zero])
    )
    ratio_zero = np.exp(log0 - log0thin)
    bracket = -r * q * mu / (r + q * mu) + ratio_zero * a - (1 - ratio_zero) * ratio * a
    score_m[partial_zero] = (
        np.exp(
            np.log(active[partial_zero])
            + log0thin[partial_zero]
            - np.log(nonzero[partial_zero])
            - logp[partial_zero]
        )
        * bracket[partial_zero]
    )
    full_zero = ~positive & (q == 1)
    logp[full_zero], score_h[full_zero] = -h[full_zero], -h[full_zero]
    return logp, score_h, score_m


def count_convolution(first, second, count):
    """Separate exact zero mass so FFT roundoff cannot erase rare positive counts."""
    a, b = first.copy(), second.copy()
    a0, b0 = a[0], b[0]
    a[0], b[0] = 0, 0
    result = np.maximum(fftconvolve(a, b)[: count + 1], 0)
    result[: len(b)] += a0 * b[: len(result)]
    result[: len(a)] += b0 * a[: len(result)]
    result[0] = a0 * b0
    return result


def tilted_coarse_probability(count, hazard, mean, size, fractions, state, scores=True):
    """Alias-free count coefficient with exponential tilting and finite convolution.

    Truncating each hourly polynomial at the observed total preserves that total's probability
    exactly. Tilting makes rare-count coefficients numerically resolvable. Negative roundoff in
    nonnegative FFT convolutions is set to zero.
    """
    if count <= max(20, len(hazard)):
        y = np.arange(count + 1)
        logp, score_h, score_m = thinned_hour_logpmf(
            y[None, :], hazard[:, None], mean[:, None], size[:, None], fractions[:, None], state
        )
        difference = y[:, None] - y[None, :]
        prefix = [np.r_[0.0, np.repeat(-np.inf, count)]]
        for hour in logp:
            terms = prefix[-1][None, :] + hour[np.maximum(difference, 0)]
            prefix.append(logsumexp(np.where(difference >= 0, terms, -np.inf), axis=1))
        log_probability = prefix[-1][count]
        if not scores:
            return log_probability
        suffix = [None] * (len(logp) + 1)
        suffix[-1] = np.r_[0.0, np.repeat(-np.inf, count)]
        for i in range(len(logp) - 1, -1, -1):
            terms = suffix[i + 1][None, :] + logp[i][np.maximum(difference, 0)]
            suffix[i] = logsumexp(np.where(difference >= 0, terms, -np.inf), axis=1)
        dh, dm = np.zeros(len(logp)), np.zeros(len(logp))
        for i in range(len(logp)):
            terms = prefix[i][None, :] + suffix[i + 1][np.maximum(difference, 0)]
            rest = logsumexp(np.where(difference >= 0, terms, -np.inf), axis=1)
            weights = np.exp(logp[i] + rest[::-1] - log_probability)
            dh[i], dm[i] = weights @ score_h[i], weights @ score_m[i]
        return log_probability, dh, dm
    h, mu, r, q = np.broadcast_arrays(state * hazard, state * mean, size, fractions)
    active = -np.expm1(-h)
    zero = np.exp(-r * np.log1p(mu / r))
    nonzero = -np.expm1(-r * np.log1p(mu / r))

    log0 = -r * np.log1p(mu / r)

    def pgf(radius):
        denominator = 1 + q * mu / r * (1 - radius)
        log_nb = -r * np.log(denominator)
        relative = (
            r * np.log1p(-mu / (r + mu) * (1 - q + q * radius)) if radius <= 0.5 else log0 - log_nb
        )
        log_difference = log_nb + np.log(-np.expm1(relative))
        log_value = np.logaddexp(-h, np.log(active) + log_difference - np.log(nonzero))
        log_derivative = (
            np.log(radius)
            + np.log(active)
            + log_nb
            + np.log(q * mu)
            - np.log(denominator)
            - np.log(nonzero)
            - log_value
        )
        return log_value, np.exp(log_derivative).sum()

    upper = (1 + r / (q * mu)).min()
    # Stay inside the NB singularity despite reciprocal and contour rounding.
    endpoint = upper
    for _ in range(4):
        endpoint = np.nextafter(endpoint, 1.0)
    # Some extremely rare mixtures have no representable saddle before the NB pole.
    # Coefficient extraction remains exact at radius one with zero mass separated.
    radius = (
        brentq(lambda z: pgf(z)[1] - count, 1e-12, endpoint, xtol=1e-14)
        if pgf(endpoint)[1] > count
        else 1.0
    )
    log_normalizer = pgf(radius)[0]
    y = np.arange(count + 1)
    logp, score_h, score_m = thinned_hour_logpmf(
        y[None, :], hazard[:, None], mean[:, None], size[:, None], fractions[:, None], state
    )
    tilted = np.exp(logp + y * np.log(radius) - log_normalizer[:, None])
    prefix = [np.array([1.0])]
    for values in tilted:
        prefix.append(count_convolution(prefix[-1], values, count))
    probability = prefix[-1][count]
    log_probability = np.log(probability) + log_normalizer.sum() - count * np.log(radius)
    if not scores:
        return log_probability
    suffix = [None] * (len(tilted) + 1)
    suffix[-1] = np.array([1.0])
    for i in range(len(tilted) - 1, -1, -1):
        suffix[i] = count_convolution(tilted[i], suffix[i + 1], count)
    dh, dm = np.zeros(len(tilted)), np.zeros(len(tilted))
    for i in range(len(tilted)):
        rest = count_convolution(prefix[i], suffix[i + 1], count)
        weights = tilted[i, : len(rest)] * rest[::-1] / probability
        # Missing high coefficients of a short rest polynomial correspond to low k.
        if len(rest) < count + 1:
            weights = tilted[i, count + 1 - len(rest) :] * rest[::-1] / probability
            dh[i] = weights @ score_h[i, count + 1 - len(rest) :]
            dm[i] = weights @ score_m[i, count + 1 - len(rest) :]
        else:
            dh[i], dm[i] = weights @ score_h[i], weights @ score_m[i]
    return log_probability, dh, dm
