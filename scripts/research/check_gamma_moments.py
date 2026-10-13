"""Check predictive Gamma moments independently, including large occurrence hazards."""

import numpy as np
from gamma_count_moments import gamma_hour_moments
from scipy.integrate import quad
from scipy.special import gammaln

for shape in [0.05, 0.5, 5]:
    for hazard, mean, size, fraction in [(1e-4, 0.001, 0.5, 1), (1, 5, 2, 0.4), (1e8, 1000, 1, 1)]:
        predicted, active = gamma_hour_moments(
            shape,
            shape,
            np.array([hazard]),
            np.array([mean]),
            np.array([size]),
            np.array([fraction]),
            243,
        )

        def integrand(t, occurrence):
            g = np.exp(t)
            prior = np.exp(shape * np.log(shape) - gammaln(shape) + shape * t - shape * g)
            gate = -np.expm1(-hazard * g)
            nonzero = -np.expm1(-size * np.log1p(mean * g / size))
            return (
                prior
                * gate
                * (
                    (-np.expm1(-size * np.log1p(fraction * mean * g / size))) / nonzero
                    if occurrence
                    else fraction * mean * g / nonzero
                )
            )

        expected = np.array(
            [
                quad(lambda t: integrand(t, kind), -600, 0, epsabs=1e-9)[0]
                + quad(lambda t: integrand(t, kind), 0, 20, epsabs=1e-9)[0]
                for kind in [False, True]
            ]
        )
        np.testing.assert_allclose([predicted[0], active[0]], expected, atol=1e-5, rtol=1e-4)
print(
    "Stable predictive means and occurrence probabilities pass independent integration, including high hazards."
)
