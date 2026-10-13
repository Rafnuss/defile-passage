"""Check adjustment identities, information weights and bounded responses."""

import numpy as np
from adjustment_functions import PARAMETERS, adjusted_count

missing = np.array([2.0, 20.0, 200.0])
retained = np.array([1.0, 10.0, 100.0])
for function, parameters in PARAMETERS.items():
    off = np.inf if function == "count_shrinkage" else 0
    assert np.allclose(adjusted_count(missing, retained, retained * 3, function, off), missing)
    for parameter in parameters:
        assert np.allclose(
            adjusted_count(missing, retained, retained, function, parameter), missing
        )
        low = adjusted_count(missing, retained, np.zeros(3), function, parameter)
        high = adjusted_count(missing, retained, retained * 4, function, parameter)
        assert np.all(low >= 0) and np.all(high >= low)
        if function != "coverage_blend":
            assert np.allclose(
                adjusted_count(2 * missing, retained, retained * 3, function, parameter),
                2 * adjusted_count(missing, retained, retained * 3, function, parameter),
            )


# Fixed s already changes the evidence weight with expected retained count.
s = 10
observed = retained * 2
weight = retained / (retained + s)
expected = missing * (1 + weight * (observed / retained - 1))
assert np.allclose(adjusted_count(missing, retained, observed, "count_shrinkage", s), expected)
assert np.all(np.diff(weight) > 0)

# Relative coverage is an explicit extra choice, not an implicit physical requirement.
a = adjusted_count(missing, retained, observed, "coverage_blend", 1) / missing
b = adjusted_count(2 * missing, retained, observed, "coverage_blend", 1) / (2 * missing)
assert np.all(a > b)
for beta in PARAMETERS["bounded_response"]:
    assert np.allclose(
        adjusted_count(missing, retained, np.zeros(3), "bounded_response", beta),
        missing * np.exp(-beta),
    )
    assert np.all(
        adjusted_count(missing, retained, retained * 1e6, "bounded_response", beta)
        <= missing * np.exp(beta)
    )
print(
    "Adjustment checks passed: neutral limits, monotonicity, shrinkage identity, coverage and boundedness."
)
