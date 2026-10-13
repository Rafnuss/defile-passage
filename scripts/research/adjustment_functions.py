"""Small alternative empirical retained-count response functions."""

import numpy as np
from simple_rate_prediction import SHRINKAGE, retained_prediction

PARAMETERS = {
    "count_shrinkage": SHRINKAGE,
    "constant_blend": np.array([0, 0.25, 0.5, 0.75, 1]),
    "coverage_blend": np.array([0, 0.25, 0.5, 0.75, 1]),
    "bounded_response": np.array([0, 0.25, 0.5, 1, 2]),
}


def adjusted_count(missing_mean, retained_mean, retained_count, function, parameter):
    """Change only the missing prediction; retained counts remain observed."""
    if function == "count_shrinkage":
        return retained_prediction(missing_mean, retained_mean, retained_count, parameter)
    if function == "bounded_response":
        return missing_mean * np.exp(
            parameter * (retained_count - retained_mean) / (retained_count + retained_mean)
        )
    weight = parameter
    if function == "coverage_blend":
        weight = weight * retained_mean / (retained_mean + missing_mean)
    return missing_mean * (1 + weight * (retained_count / retained_mean - 1))
