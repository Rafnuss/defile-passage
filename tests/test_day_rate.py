"""Check the research daily multiplier against independent numerical calculations."""

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import check_grad
from scipy.special import gammaln
from scipy.stats import nbinom

from defile_passage.day_rate import day_precision, gamma_nb_posterior, nb_day, poisson_day


@pytest.mark.parametrize("likelihood,extra", [(poisson_day, [0.2]), (nb_day, [0.2, -0.7])])
def test_integrated_gradients(likelihood, extra):
    X = np.array([[1, -1], [1, 0.5], [1, 1], [1, 0.2]])
    y = np.array([0, 7, 1, 0])
    exposure = np.array([0.3, 1, 0.8, 1])
    starts = np.array([0, 2])
    penalty = np.diag([0, 0.2])
    parameters = np.r_[[0.5, -0.2], extra]
    args = X, exposure, y, starts, penalty
    error = check_grad(
        lambda p: likelihood(p, *args)[0],
        lambda p: likelihood(p, *args)[1],
        parameters,
    )
    assert error < 2e-5


@pytest.mark.parametrize(
    "shape,counts", [(0.02, [0, 0]), (0.05, [0, 0]), (0.7, [3, 12]), (30, [200, 4])]
)
def test_nb_quadrature_against_direct_integration(shape, counts):
    mu = np.array([4.0, 8.0])
    sizes = np.array([0.4, 1.2])
    counts = np.array(counts)
    marginal, z, weights = gamma_nb_posterior(mu, counts, sizes, np.array([0]), shape)

    def log_integrand(z):
        denominator = np.logaddexp(np.log(sizes), np.log(mu) + z)
        log_probability = (
            gammaln(counts + sizes)
            - gammaln(sizes)
            - gammaln(counts + 1)
            + sizes * (np.log(sizes) - denominator)
            + counts * (np.log(mu) + z - denominator)
        ).sum()
        return np.exp(
            shape * np.log(shape)
            - gammaln(shape)
            + shape * z
            - shape * np.exp(z)
            + log_probability
        )

    value = sum(
        quad(log_integrand, left, right, epsabs=1e-25, epsrel=1e-10)[0]
        for left, right in [(-2000, -40), (-40, 0), (0, 40)]
    )
    assert marginal[0] == pytest.approx(np.log(value), abs=2e-6)
    fine, _, _ = gamma_nb_posterior(mu, counts, sizes, np.array([0]), shape, order=121)
    assert marginal[0] == pytest.approx(fine[0], abs=2e-6)
    assert weights.sum() == pytest.approx(1)
    assert np.sum(weights * np.exp(z)) > 0


def test_poisson_gamma_aggregation_and_precision():
    X = np.array([[1, -0.5], [1, 0.5]])
    y = np.array([2, 5])
    exposure = np.array([0.3, 0.7])
    beta = np.array([1.0, 0.2])
    shape = 1.4
    mu = exposure * np.exp(X @ beta)
    objective, _ = poisson_day(
        np.r_[beta, np.log(shape)], X, exposure, y, np.array([0]), np.zeros((2, 2))
    )
    # Total NB count, followed by multinomial allocation, is the same joint distribution.
    total = nbinom.logpmf(y.sum(), shape, shape / (shape + mu.sum()))
    allocation = gammaln(y.sum() + 1) - gammaln(y + 1).sum() + (y * np.log(mu / mu.sum())).sum()
    assert -objective == pytest.approx(total + allocation)
    h = 1e-5
    numerical = np.column_stack(
        [
            (
                poisson_day(
                    np.r_[beta + np.eye(2)[j] * h, np.log(shape)],
                    X,
                    exposure,
                    y,
                    np.array([0]),
                    np.zeros((2, 2)),
                )[1][:2]
                - poisson_day(
                    np.r_[beta - np.eye(2)[j] * h, np.log(shape)],
                    X,
                    exposure,
                    y,
                    np.array([0]),
                    np.zeros((2, 2)),
                )[1][:2]
            )
            / (2 * h)
            for j in range(2)
        ]
    )
    precision = day_precision(
        beta, X, exposure, y, np.array([0]), np.zeros((2, 2)), shape, None, np.zeros(2)
    )
    np.testing.assert_allclose(precision, numerical, atol=1e-8)


def test_nb_integrated_precision():
    X = np.array([[1, -0.5], [1, 0.5]])
    y = np.array([2, 5])
    exposure = np.array([0.3, 0.7])
    beta = np.array([1.0, 0.2])
    shape, kappa = 1.4, 0.8
    h = 1e-5
    numerical = np.column_stack(
        [
            (
                nb_day(
                    np.r_[beta + np.eye(2)[j] * h, np.log([shape, kappa])],
                    X,
                    exposure,
                    y,
                    np.array([0]),
                    np.zeros((2, 2)),
                )[1][:2]
                - nb_day(
                    np.r_[beta - np.eye(2)[j] * h, np.log([shape, kappa])],
                    X,
                    exposure,
                    y,
                    np.array([0]),
                    np.zeros((2, 2)),
                )[1][:2]
            )
            / (2 * h)
            for j in range(2)
        ]
    )
    precision = day_precision(
        beta, X, exposure, y, np.array([0]), np.zeros((2, 2)), shape, kappa, np.zeros(2)
    )
    np.testing.assert_allclose(precision, numerical, atol=1e-6)


@pytest.mark.parametrize("shape", [0.02, 0.5, 10])
def test_daily_multiplier_prior_mean_is_one(shape):
    # Vanishing count intensity makes the posterior converge to the specified prior.
    _, z, weights = gamma_nb_posterior(
        np.array([1e-20]), np.array([0]), np.array([1.0]), np.array([0]), shape
    )
    assert np.sum(weights * np.exp(z)) == pytest.approx(1, rel=2e-5)
    assert np.sum(weights * np.exp(2 * z)) == pytest.approx(1 + 1 / shape, rel=2e-5)


@pytest.mark.parametrize("total", [0, 5, 20])
def test_nb_exposure_shape_preserves_constant_rate_aggregation(total):
    exposure = np.array([0.3, 0.7])
    rate, kappa, shape = 4.0, 0.8, 1.2
    allocation = []
    for first in range(total + 1):
        joint, _, _ = gamma_nb_posterior(
            rate * exposure,
            np.array([first, total - first]),
            kappa * exposure,
            np.array([0]),
            shape,
        )
        allocation.append(np.exp(joint[0]))
    aggregated, _, _ = gamma_nb_posterior(
        np.array([rate]), np.array([total]), np.array([kappa]), np.array([0]), shape
    )
    assert sum(allocation) == pytest.approx(np.exp(aggregated[0]), rel=2e-6)


def test_smoothing_update_matches_gaussian_posterior_moments():
    from scipy.optimize import minimize

    from defile_passage.day_rate import smoothing_moments

    components = np.array([np.diag([0.0, 2.0, 3.0])])
    beta = np.array([1.0, 0.3, -0.4])
    covariance = np.diag([0.1, 0.2, 0.3])
    penalized = np.array([1, 2])
    args = components, beta, covariance, penalized
    assert (
        check_grad(
            lambda p: smoothing_moments(p, *args)[0],
            lambda p: smoothing_moments(p, *args)[1],
            np.array([0.2]),
        )
        < 1e-6
    )
    fit = minimize(smoothing_moments, [0.0], args=args, jac=True)
    expected = 2 / (2 * (0.3**2 + 0.2) + 3 * (0.4**2 + 0.3))
    assert np.exp(fit.x[0]) == pytest.approx(expected, rel=1e-5)


def test_laplace_evidence_equals_exact_gaussian_integral():
    from scipy.linalg import null_space

    from defile_passage.day_rate import laplace_score

    X = np.array([[1.0, -1.0, 0.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.5], [1.0, 0.5, -1.0]])
    y = np.array([0.0, 1.0, 3.0, 2.0])
    penalty = np.diag([0.0, 2.0, 3.0])
    information = X.T @ X + penalty
    beta = np.linalg.solve(information, X.T @ y)
    objective = ((y - X @ beta) @ (y - X @ beta) + beta @ penalty @ beta) / 2
    approximate = laplace_score(objective, information, penalty, np.array([1, 2]))
    projection = null_space(X[:, :1].T)
    marginal = (
        projection.T
        @ (np.eye(len(y)) + X[:, 1:] @ np.linalg.inv(penalty[1:, 1:]) @ X[:, 1:].T)
        @ projection
    )
    residual = projection.T @ y
    exact = (residual @ np.linalg.solve(marginal, residual) + np.linalg.slogdet(marginal)[1]) / 2
    assert approximate == pytest.approx(exact + np.log(X[:, 0] @ X[:, 0]) / 2)
