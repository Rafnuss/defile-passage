"""Check weighted mixed-interval gradients and known constant-rate solutions."""

from unittest.mock import patch

import numpy as np
from scipy.optimize import minimize
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

A = csr_matrix(np.diag([0.25, 1, 4, 8]))
duration = np.asarray(A.sum(axis=1)).ravel()
y = np.array([0, 2, 24, 12])
for power in [0, 0.25, 0.5]:
    weights = duration**power
    X = np.ones((4, 1))
    fit, objective = fit_rate(X, A, y, np.zeros((1, 1)), 1.5, weights)
    expected_rate = (weights * y / np.sqrt(duration)).sum() / (weights * np.sqrt(duration)).sum()
    assert np.allclose(np.exp(fit.x[0]), expected_rate, rtol=1e-6)
    if power == 0.5:
        assert np.allclose(np.exp(fit.x[0]), y.sum() / duration.sum(), rtol=1e-6)
    X = np.column_stack([np.ones(4), [-1, -0.5, 0.5, 1]])
    with patch("simple_rate_model.minimize", wraps=minimize) as optimizer:
        fit, objective = fit_rate(X, A, y, np.diag([0, 1]), 1.5, weights, solver="trust-exact")
    assert abs(fit.jac).max() < 0.001
    assert check_rate_gradient(objective, np.array([2.0, -0.3])) < 1e-6
    assert check_rate_gradient(objective, fit.x) < 1e-6
    point = np.array([2.0, -0.3])
    directions = np.eye(2) * 1e-5
    numerical_hessian = np.column_stack(
        [(objective(point + d)[1] - objective(point - d)[1]) / 2e-5 for d in directions]
    )
    assert np.allclose(
        optimizer.call_args.kwargs["hess"](point), numerical_hessian, atol=1e-7, rtol=1e-7
    )
    if power == 0:
        fit, _ = fit_rate(X, A, y, np.diag([0, 1]), 1.5, weights)
        unchanged, _ = fit_rate(X, A, y, np.diag([0, 1]), 1.5)
        assert np.allclose(fit.x, unchanged.x, atol=1e-10, rtol=1e-10)
print("Weighted derivatives, duration scaling, constant-rate solutions and default replay pass.")
