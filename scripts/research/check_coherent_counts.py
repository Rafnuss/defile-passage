"""Validate thinning scores and coarse likelihood without using the fitter."""

import numpy as np
from coherent_hour_counts import thinned_hour_logpmf, tilted_coarse_probability
from scipy.signal import convolve
from scipy.special import logsumexp
from scipy.stats import nbinom

h, mu, r, q = (
    np.array([0.2, 1.2]),
    np.array([4.0, 10.0]),
    np.array([0.5, 2.0]),
    np.array([0.3, 1.0]),
)
for y in [0, 1, 20]:
    logp, dh, dm = thinned_hour_logpmf(y, h, mu, r, q, 1)
    step = 1e-5
    for rate, score, index in [(h, dh, 0), (mu, dm, 1)]:
        plus, minus = [h.copy(), mu.copy()], [h.copy(), mu.copy()]
        plus[index] = rate * np.exp(step)
        minus[index] = rate * np.exp(-step)
        numerical = (
            thinned_hour_logpmf(y, *plus, r, q, 1)[0] - thinned_hour_logpmf(y, *minus, r, q, 1)[0]
        ) / (2 * step)
        np.testing.assert_allclose(score, numerical, atol=1e-7)
for y in [1, 20, 100]:
    logp, dh, dm = tilted_coarse_probability(y, h, mu, r, q, 1)
    probabilities = np.exp(
        thinned_hour_logpmf(
            np.arange(y + 1)[None, :], h[:, None], mu[:, None], r[:, None], q[:, None], 1
        )[0]
    )
    expected = convolve(probabilities[0], probabilities[1], method="direct")[y]
    np.testing.assert_allclose(np.exp(logp), expected, rtol=1e-8)
    for i in range(2):
        for rate, score, index in [(h, dh, 0), (mu, dm, 1)]:
            plus, minus = [h.copy(), mu.copy()], [h.copy(), mu.copy()]
            plus[index][i] *= np.exp(1e-5)
            minus[index][i] *= np.exp(-1e-5)
            numerical = (
                tilted_coarse_probability(y, *plus, r, q, 1, scores=False)
                - tilted_coarse_probability(y, *minus, r, q, 1, scores=False)
            ) / (2e-5)
            np.testing.assert_allclose(score[i], numerical, atol=1e-6)
print("Canonical thinning and coarse convolution probabilities and gradients passed.")

# Rare large totals stay finite on the log scale without probability flooring.
y = 1000
h, mu, r, q = np.array([1000.0, 1000.0]), np.array([4.0, 4.0]), np.array([2.0, 2.0]), np.ones(2)
logp = tilted_coarse_probability(y, h, mu, r, q, 1, scores=False)
p0 = nbinom.pmf(0, 2, 2 / 6)
expected = logsumexp(
    [nbinom.logpmf(y, 4, 2 / 6), np.log(2 * p0) + nbinom.logpmf(y, 2, 2 / 6)], b=[1, -1]
) - 2 * np.log1p(-p0)
np.testing.assert_allclose(logp, expected, atol=1e-6)
print("Rare large survey totals retain finite, accurate log probabilities.")

# Extreme rate contrasts exercise stable PGF differences near the contour origin.
for mean, size, total in [
    (np.array([1e-18, 1e-18]), np.array([0.02, 0.02]), 26),
    (np.array([1e-12, 1e13]), np.array([0.02, 50.0]), 100),
]:
    hazard, fraction = np.array([1000.0, 2000.0]), np.array([1.0, 0.4])
    logp = thinned_hour_logpmf(
        np.arange(total + 1)[None, :],
        hazard[:, None],
        mean[:, None],
        size[:, None],
        fraction[:, None],
        1,
    )[0]
    reference = logsumexp(logp[0] + logp[1, ::-1])
    calculated, dh, dm = tilted_coarse_probability(total, hazard, mean, size, fraction, 1)
    np.testing.assert_allclose(calculated, reference, atol=1e-7)
    assert np.isfinite(dh).all() and np.isfinite(dm).all()
print("Extreme rate contrasts retain finite coarse likelihoods and gradients.")

# Rare positive counts must survive a mixture dominated by exact zero mass.
for count in [26, 100]:
    hazard, mean, size, fractions = (
        np.array([1e-20, 1e-20]),
        np.array([1e13, 1e13]),
        np.array([0.05, 0.05]),
        np.ones(2),
    )
    y = np.arange(count + 1)
    logp, _, _ = thinned_hour_logpmf(
        y[None, :], hazard[:, None], mean[:, None], size[:, None], fractions[:, None], 1.0
    )
    reference = logsumexp(logp[0] + logp[1, ::-1])
    actual, dh, dm = tilted_coarse_probability(count, hazard, mean, size, fractions, 1.0)
    np.testing.assert_allclose(actual, reference, atol=1e-8, rtol=0)
    np.testing.assert_allclose(dh.sum(), 1.0, atol=1e-8, rtol=0)
print("Rare positive probabilities survive dominant zero mass without FFT cancellation.")
