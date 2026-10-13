"""Numerical checks shared by the activity-model experiments."""

import numpy as np


def directional_gradient_check(objective, parameters, seed=20261011):
    """Compare analytic derivatives with central differences in fixed directions."""
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(8, len(parameters)))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    _, gradient = objective(parameters)
    analytic = directions @ gradient
    numerical = np.array(
        [
            (
                objective(parameters + 1e-4 * direction)[0]
                - objective(parameters - 1e-4 * direction)[0]
            )
            / 2e-4
            for direction in directions
        ]
    )
    return np.max(np.abs(analytic - numerical) / np.maximum(1, np.abs(numerical)))
