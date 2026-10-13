"""Stable Gamma predictive moments with the near-zero constant integrated exactly."""

from itertools import product

import numpy as np
from shared_activity_prediction import gamma_quadrature


def gamma_hour_moments(shape, rate, hazard, mean, size, fractions=1, order=121):
    hazard, mean, size, fractions = np.broadcast_arrays(hazard, mean, size, fractions)
    nodes, log_weights = gamma_quadrature(shape + 1, order)
    nodes = nodes * (shape + 1) / rate
    gh, gm = hazard[:, None] * nodes, mean[:, None] * nodes
    gate = -np.expm1(-gh)
    nonzero = -np.expm1(-size[:, None] * np.log1p(gm / size[:, None]))
    positive_mean = gm / nonzero
    gate_probability = -np.expm1(-shape * np.log1p(hazard / rate))
    expected = fractions * (
        gate_probability
        + shape / rate * (gate * (positive_mean - 1) / nodes) @ np.exp(log_weights)
    )
    thin_nonzero = -np.expm1(-size[:, None] * np.log1p(fractions[:, None] * gm / size[:, None]))
    active = fractions * gate_probability + shape / rate * (
        gate * (thin_nonzero / nonzero - fractions[:, None]) / nodes
    ) @ np.exp(log_weights)
    return expected, active


def gamma_interval_active(shape, rate, hazard, mean, size, fractions, order=121):
    """Integrate the constant-flock limit exactly, including partial end hours."""
    nodes, log_weights = gamma_quadrature(shape + 1, order)
    nodes = nodes * (shape + 1) / rate
    gh, gm = hazard[:, None] * nodes, mean[:, None] * nodes
    gate = -np.expm1(-gh)
    nonzero = -np.expm1(-size * np.log1p(gm / size))
    thin_nonzero = -np.expm1(-size * np.log1p(fractions[:, None] * gm / size))
    actual_zero = (1 - gate * thin_nonzero / nonzero).prod(axis=0)
    limit_zero = (1 - fractions[:, None] * gate).prod(axis=0)
    partial = np.flatnonzero(fractions < 1)
    full_hazard = hazard[fractions == 1].sum()
    expected_zero = 0.0
    for selected in product([0, 1], repeat=len(partial)):
        chosen = np.array(selected, dtype=bool)
        probability = np.prod(np.where(chosen, fractions[partial], 1 - fractions[partial]))
        total = full_hazard + hazard[partial][chosen].sum()
        expected_zero += probability * np.exp(-shape * np.log1p(total / rate))
    return (
        1
        - expected_zero
        + shape / rate * ((limit_zero - actual_zero) / nodes) @ np.exp(log_weights)
    )
