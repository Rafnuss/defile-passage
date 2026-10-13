"""Numerical checks of the mixed-scale likelihood, independent of fit outputs."""

import numpy as np
from mixed_interval_likelihood import interval_pgf, interval_probability
from scipy.stats import nbinom

hour = dict(hazard=np.array([0.7]), mean=np.array([8.0]), size=np.array([2.0]))
active = -np.expm1(-0.7)
zero = nbinom.pmf(0, 2, 2 / 10)
for fraction in [0.2, 0.6, 1.0]:
    p = 2 / (2 + fraction * 8)
    expected = active * nbinom.pmf(np.arange(80), 2, p) / (1 - zero)
    expected[0] = 1 - active + active * (nbinom.pmf(0, 2, p) - zero) / (1 - zero)
    calculated = np.array(
        [interval_probability(y, **hour, fractions=[fraction], day_state=1) for y in range(80)]
    )
    np.testing.assert_allclose(calculated, expected, atol=1e-9)

# Two distinct hours aggregate by convolution, retaining different weather rates.
first = np.array([interval_probability(y, **hour, fractions=[1], day_state=1) for y in range(100)])
second_hour = dict(hazard=np.array([0.2]), mean=np.array([3.0]), size=np.array([1.5]))
second = np.array(
    [interval_probability(y, **second_hour, fractions=[0.4], day_state=1) for y in range(100)]
)
aggregate = dict(hazard=[0.7, 0.2], mean=[8, 3], size=[2, 1.5], fractions=[1, 0.4])
calculated = np.array([interval_probability(y, **aggregate, day_state=1) for y in range(100)])
np.testing.assert_allclose(calculated, np.convolve(first, second)[:100], atol=1e-9)
for y in [1, 20, 80]:
    np.testing.assert_allclose(
        interval_probability(y, **aggregate, day_state=1, fft_size=256),
        interval_probability(y, **aggregate, day_state=1, fft_size=512),
        atol=1e-9,
    )
print("Mixed-interval thinning, convolution and FFT sensitivity checks passed.")
