"""Independent checks for exposure, mixed-interval derivatives and high counts."""

import numpy as np
from scipy.optimize import check_grad
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

# A constant rate has a known maximum-likelihood estimate at any temporal scale.
X = np.ones((6, 1))
A = csr_matrix([[0.25, 0, 0, 0, 0, 0], [0, 0.75, 1, 0, 0, 0], [0, 0, 0, 1, 0.5, 0.5]])
y = np.array([0, 14, 20])
fit, objective = fit_rate(X, A, y, np.zeros((1, 1)))
assert np.allclose(np.exp(fit.x[0]), y.sum() / A.sum(), rtol=1e-7)
assert np.allclose((A @ np.exp(X @ fit.x)).sum(), y.sum(), rtol=1e-7)

# Use direct finite differences away from the optimum for intact mixed totals.
X = np.column_stack([np.ones(6), [-1, -0.5, 0, 0.2, 0.7, 1]])
penalty = np.diag([0, 1])
fit, objective = fit_rate(X, A, y, penalty)
point = np.array([2.0, -0.3])
error = check_grad(lambda b: objective(b)[0], lambda b: objective(b)[1], point, epsilon=1e-6)
assert error < 1e-4, error
assert np.abs(fit.jac).max() < 1e-4
fit, objective = fit_rate(X, A, y, penalty, variance_power=1.5)
error = check_grad(lambda b: objective(b)[0], lambda b: objective(b)[1], point, epsilon=1e-6)
assert error < 1e-4, error
assert np.abs(fit.jac).max() < 1e-4

# Large bird totals should not make finite-difference truncation a false failure.
y = np.array([1_000_000, 4_000_000, 2_000_000])
fit, objective = fit_rate(X, A, y, penalty)
assert np.abs(fit.jac).max() < 0.001, fit.jac
assert check_rate_gradient(objective, fit.x) < 0.001
print(
    "Simple rate checks passed: exposure, intact aggregation, mixed derivatives and large counts."
)
