"""Independent curvature and constrained-variance checks for saved-fit diagnosis."""

import numpy as np
from daily_passage_diagnostics import conditional_daily_variance, observed_information
from daily_passage_model import ar1_penalty, center_daily, daily_objective
from scipy.linalg import solve
from scipy.sparse import csr_matrix

years = np.repeat([0, 1], 6)
day = np.array([0, 0, 1, 4, 5, 6, 7, 10, 11])
X = np.column_stack([np.ones(len(day)), np.linspace(-1, 1, len(day))])
A = csr_matrix(
    [
        [0.5, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0.5, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0.75, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0.5, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 1],
    ]
)
y, P = np.array([0, 8, 30, 5, 18]), np.diag([0, 1])
Q = ar1_penalty(years)
Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), len(years)))
point = np.r_[2.0, -0.3, center_daily(np.linspace(-0.4, 0.8, len(years)), years)]
objective = daily_objective(X, A, y, P, Q, day, years)
rate = np.exp(X @ point[:2] + point[2:][day])
bb, cross, uu = observed_information(X, A, y, P, Q, Z, rate)
H = np.block([[bb, cross], [cross.T, uu.toarray()]])
projection = np.eye(len(point))
for year in [0, 1]:
    index = np.flatnonzero(years == year) + 2
    projection[np.ix_(index, index)] -= 1 / len(index)
H = projection @ H @ projection
finite = np.column_stack(
    [
        (objective(point + 1e-5 * d)[1] - objective(point - 1e-5 * d)[1]) / (2e-5)
        for d in np.eye(len(point))
    ]
)
assert np.allclose(H, finite, atol=1e-7, rtol=1e-7)
C = csr_matrix((np.ones(len(years)), (years, np.arange(len(years))))).toarray()
KKT = np.block([[uu.toarray(), C.T], [C, np.zeros((2, 2))]])
inverse = solve(KKT, np.vstack([np.eye(len(years)), np.zeros((2, len(years)))]))
variance = conditional_daily_variance(uu, years)
assert np.allclose(variance, np.diag(inverse[: len(years)]), atol=1e-12)
assert (variance > 0).all()
print(
    "Observed Hessian matches independent gradient differences; centered variance matches dense KKT."
)
