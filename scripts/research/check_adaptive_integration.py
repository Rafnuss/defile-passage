"""Compare posterior-centered daily integration with independent adaptive quadrature."""

import numpy as np
from adaptive_daily_integration import adaptive_hurdle_log_probability, hurdle_log_rows
from scipy.integrate import quad
from scipy.optimize import minimize_scalar
from scipy.special import gammaln

for shape in [0.05, 0.5, 5, 10000]:
    for counts in [np.array([0, 1, 3]), np.array([0, 20, 200])]:
        hazard, mean, size = np.array([3, 0.1, 2]), np.array([2, 5, 40]), np.array([1, 2, 0.5])

        def log_density(t):
            prior = shape * np.log(shape) - gammaln(shape) + shape * t - shape * np.exp(t)
            return prior + hurdle_log_rows(np.array([np.exp(t)]), counts, hazard, mean, size).sum()

        mode = minimize_scalar(lambda t: -log_density(t), bounds=(-40, 15), method="bounded").x
        peak = log_density(mode)
        # Split at the mode so the independent integrator resolves high-shape peaks.
        integral = (
            quad(lambda t: np.exp(log_density(t) - peak), -40, mode, epsabs=1e-11)[0]
            + quad(lambda t: np.exp(log_density(t) - peak), mode, 15, epsabs=1e-11)[0]
        )
        reference = np.log(integral) + peak
        candidate = adaptive_hurdle_log_probability(shape, counts, hazard, mean, size, order=63)
        np.testing.assert_allclose(candidate, reference, atol=1e-6, rtol=0)
print(
    "Posterior-centered integration agrees with independent quadrature across sparse, flocked and high-shape cases."
)


from adaptive_daily_integration import adaptive_hurdle_rule, adaptive_hurdle_rules
from scipy.special import logsumexp

rng = np.random.default_rng(20261012)
y, size = np.array([0, 1, 20]), np.array([1.0, 2.0, 0.5])
hazard = np.exp(rng.normal(size=(3, 20)))
mean = np.exp(rng.normal(2, 2, size=(3, 20)))
for shape in [0.05, 0.5, 5, 10000]:
    nodes, weights = adaptive_hurdle_rules(shape, y, hazard, mean, size, 63)
    for i in range(20):
        single_nodes, single_weights = adaptive_hurdle_rule(
            shape, y, hazard[:, i], mean[:, i], size, 63
        )
        a = logsumexp(
            weights[:, i]
            + hurdle_log_rows(nodes[:, i], y, hazard[:, i], mean[:, i], size).sum(axis=0)
        )
        b = logsumexp(
            single_weights
            + hurdle_log_rows(single_nodes, y, hazard[:, i], mean[:, i], size).sum(axis=0)
        )
        np.testing.assert_allclose(a, b, atol=1e-7, rtol=0)
print("Batched posterior rules agree with individually optimized rules.")

from adaptive_daily_integration import flat_hurdle_state_draws

# A positive singleton with near-certain gate and tiny mean leaves a flat Gamma tail.
shape = 0.05
counts, hazard, mean, size = (
    np.array([1]),
    np.array([[1e12]]),
    np.array([[1e-12]]),
    np.array([1.0]),
)
u = np.array([0.5])
a = flat_hurdle_state_draws(shape, counts, hazard, mean, size, u)
b = flat_hurdle_state_draws(shape, counts, hazard, mean, size, u, step=0.025)
np.testing.assert_allclose(a, b, rtol=0.001)


def joint(t):
    return np.exp(
        shape * np.log(shape)
        - gammaln(shape)
        + shape * t
        - shape * np.exp(t)
        + hurdle_log_rows(np.array([np.exp(t)]), counts, hazard[:, 0], mean[:, 0], size).sum()
    )


norm = quad(joint, -100, 40, epsabs=1e-10)[0]
p = quad(joint, -100, np.log(b[0]), epsabs=1e-10)[0] / norm
np.testing.assert_allclose(p, 0.5, atol=1e-4)
print("Flat posterior CDF sampling passes grid refinement and independent integration.")
