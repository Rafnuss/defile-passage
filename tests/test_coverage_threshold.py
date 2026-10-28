"""Check deterministic predictive means against independent numerical integration."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.special import expit
from scipy.stats import norm

folder = Path(__file__).parents[1] / "scripts/hierarchical"
sys.path.insert(0, str(folder))
spec = importlib.util.spec_from_file_location(
    "coverage_threshold", folder / "coverage_threshold.py"
)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
sys.path.pop(0)


def test_predictive_mean_integrates_correlated_coefficient_uncertainty():
    X = np.array([[1, -0.5], [1, 1], [1, 0.3]])
    A = np.array([[0.4, 0], [0.2, 0.3]])
    beta = np.array([3.0, -0.7])
    fit = SimpleNamespace(
        design=SimpleNamespace(X=lambda year, doy: X),
        beta=beta,
        H=SimpleNamespace(draws=lambda z: A @ z),
        theta=2.3,
    )
    target = pd.DataFrame(dict(year=[2020] * 3, doy=[210] * 3, c=[0, 0.02, 0.5], y=[4, 3, 20]))
    expected = []
    for row, c, y in zip(X, target.c, target.y):
        mean, sd = row @ beta, np.linalg.norm(row @ A)
        if c == 0:
            expected.append((1 + y / fit.theta) * np.exp(mean + sd**2 / 2))
        else:
            value, _ = quad(
                lambda z: (fit.theta + y)
                / c
                * expit(mean + sd * z + np.log(c / fit.theta))
                * norm.pdf(z),
                -10,
                10,
            )
            expected.append(value)
    assert np.allclose(experiment.rate_mean(fit, target), expected, rtol=1e-10)
