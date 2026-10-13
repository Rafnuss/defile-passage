"""Aggregation-consistent likelihood for intervals of a canonical hourly hurdle process.

An hourly count is zero or zero-truncated NB. Observing a fraction of that hour binomially thins
its count; disjoint fractions must allocate the SAME latent count. Conditional on the daily state,
different clock hours are independent. This is a research likelihood bridge; existing exposure-
scaled fits require refitting to it.
"""

import numpy as np
from scipy.special import logsumexp
from shared_activity_prediction import gamma_quadrature


def interval_pgf(z, hazard, mean, size, fractions, day_state):
    """PGF of one observed interval, retaining hourly weather and real coverage."""
    hazard, mean, size, fractions = np.broadcast_arrays(hazard, mean, size, fractions)
    active = -np.expm1(-day_state * hazard)
    mean = day_state * mean
    log_zero = -size * np.log1p(mean / size)
    nonzero = -np.expm1(log_zero)
    thinned = np.exp(
        -size[:, None]
        * np.log1p(mean[:, None] / size[:, None] * fractions[:, None] * (1 - np.atleast_1d(z)))
    )
    hourly = (
        1
        - active[:, None]
        + active[:, None] * (thinned - np.exp(log_zero)[:, None]) / nonzero[:, None]
    )
    return hourly.prod(axis=0)


def interval_probability(count, hazard, mean, size, fractions, day_state, fft_size=None):
    """Recover an integer count probability without allocating coarse observations.

    Exponential tilting suppresses wraparound; doubling FFT size is the numerical sensitivity
    check. All constituent hours here belong to the same civil date.
    """
    if count == 0:
        return float(interval_pgf(0, hazard, mean, size, fractions, day_state)[0].real)
    if fft_size is None:
        fft_size = 2 ** int(np.ceil(np.log2(max(256, 2 * (count + 1)))))
    radius = np.exp(-20 / fft_size)
    z = radius * np.exp(2j * np.pi * np.arange(fft_size) / fft_size)
    coefficients = np.fft.fft(interval_pgf(z, hazard, mean, size, fractions, day_state))
    return float(coefficients[count].real / fft_size / radius**count)


def day_log_likelihood(counts, intervals, shape, order=121):
    """Integrate a shared daily state over nonoverlapping observed intervals.

    Each interval supplies hazard, mean, size and fractions for its clock hours. Intervals sharing
    a clock hour require a joint multinomial likelihood instead.
    """
    nodes, weights = gamma_quadrature(shape, order)
    log_probability = np.zeros(order)
    for count, interval in zip(counts, intervals):
        probabilities = np.array(
            [interval_probability(int(count), **interval, day_state=g) for g in nodes]
        )
        log_probability += np.log(probabilities)
    return float(logsumexp(weights + log_probability))
