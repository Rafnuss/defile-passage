"""Sparse penalized scoring for a centered daily passage deviation."""

import numpy as np
from scipy.linalg import solve
from scipy.optimize import OptimizeResult
from scipy.sparse import csr_matrix, diags
from scipy.sparse.linalg import splu
from scipy.special import xlogy

CORRELATION_DAYS = 7
DAILY_SD = 0.5
MAX_ITERATIONS = 100
MAX_LINE_STEPS = 20
GRADIENT_TARGET = 1e-5
ARMIJO = 1e-4


def center_daily(values, years):
    """Remove each calendar year's mean without dropping unobserved dates."""
    return values - (np.bincount(years, weights=values) / np.bincount(years))[years]


def ar1_penalty(years, sd=DAILY_SD):
    """Stationary AR(1) precision with a separate initial value in each year."""
    rho = np.exp(-1 / CORRELATION_DAYS)
    adjacent = np.flatnonzero(years[1:] == years[:-1])
    diagonal = np.zeros(len(years))
    diagonal[np.r_[True, years[1:] != years[:-1]]] = 1 / sd**2
    diagonal[adjacent] += rho**2 / (sd**2 * (1 - rho**2))
    diagonal[adjacent + 1] += 1 / (sd**2 * (1 - rho**2))
    off = np.zeros(len(years) - 1)
    off[adjacent] = -rho / (sd**2 * (1 - rho**2))
    return diags([off, diagonal, off], [-1, 0, 1], format="csc")


def daily_objective(X, aggregation, counts, penalty, precision, day, years, variance_power=1.5):
    """Return the same working loss as the small mean, with centered day values."""
    p = X.shape[1]

    def objective(parameters):
        daily = center_daily(parameters[p:], years)
        rate = np.exp(X @ parameters[:p] + daily[day])
        mean = aggregation @ rate
        if variance_power == 1:
            loss = (mean - counts + xlogy(counts, counts / mean)).sum()
        else:
            loss = (2 * (np.sqrt(mean) - np.sqrt(counts)) ** 2 / np.sqrt(mean)).sum()
        loss += parameters[:p] @ penalty @ parameters[:p] / 2 + daily @ precision @ daily / 2
        score = (mean - counts) / mean**variance_power
        residual = rate * (aggregation.T @ score)
        shared_gradient = X.T @ residual + penalty @ parameters[:p]
        day_gradient = np.bincount(day, weights=residual, minlength=len(years)) + precision @ daily
        return loss, np.r_[shared_gradient, center_daily(day_gradient, years)]

    return objective


def scoring_information(X, aggregation, penalty, precision, day_design, rate, variance_power=1.5):
    """Positive working information; it is not the observed objective Hessian."""
    weighted = aggregation.multiply(rate)
    shared = weighted @ X
    daily = weighted @ day_design
    weights = np.asarray(aggregation @ rate) ** -variance_power
    bb = shared.T @ (weights[:, None] * shared) + penalty
    cross = (daily.T @ (weights[:, None] * shared)).T
    uu = (daily.T @ daily.multiply(weights[:, None]) + precision).tocsc()
    return bb, cross, uu, shared, daily, weights


def scoring_step(bb, cross, uu, constraints, gradient):
    """Eliminate sparse daily values, respecting exact yearly centering."""
    p = len(bb)
    inverse = splu(uu)
    rhs = np.column_stack([cross.T, gradient[p:], constraints.T.toarray()])
    solved = inverse.solve(rhs)
    inverse_constraints = solved[:, p + gradient.shape[1] :]
    constrained = solved[:, : p + gradient.shape[1]]
    constrained -= inverse_constraints @ solve(
        constraints @ inverse_constraints, constraints @ constrained, assume_a="pos"
    )
    coupling, daily_gradient = constrained[:, :p], constrained[:, p:]
    schur = bb - cross @ coupling
    shared = solve(schur, gradient[:p] - cross @ daily_gradient, assume_a="pos")
    return np.vstack([shared, daily_gradient - coupling @ shared]), schur


def directional_curvature(
    X, aggregation, counts, penalty, precision, day, rate, direction, variance_power
):
    """Exact objective curvature along a centered parameter direction."""
    p = X.shape[1]
    log_step = X @ direction[:p] + direction[p:][day]
    mean = aggregation @ rate
    first = aggregation @ (rate * log_step)
    second = aggregation @ (rate * log_step**2)
    weights = ((1 - variance_power) * mean + variance_power * counts) / mean ** (
        variance_power + 1
    )
    return (
        (weights * first**2 + (mean - counts) / mean**variance_power * second).sum()
        + direction[:p] @ penalty @ direction[:p]
        + direction[p:] @ precision @ direction[p:]
    )


def fit_daily_passage(
    X,
    aggregation,
    counts,
    penalty,
    day,
    years,
    sd=DAILY_SD,
    variance_power=1.5,
    curvature_scale=False,
):
    """Fit one fixed model with bounded scoring and objective-decreasing steps."""
    p, n = X.shape[1], len(years)
    precision = ar1_penalty(years, sd)
    constraints = csr_matrix((np.ones(n), (years, np.arange(n))))
    day_design = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), n))
    objective = daily_objective(
        X, aggregation, counts, penalty, precision, day, years, variance_power
    )
    parameters = np.zeros(p + n)
    parameters[0] = np.log(counts.sum() / aggregation.sum())
    loss, gradient = objective(parameters)
    history = [dict(iteration=0, loss=loss, gradient=abs(gradient).max(), step=0)]
    message = "iteration_limit"
    for iteration in range(1, MAX_ITERATIONS + 1):
        if abs(gradient).max() < GRADIENT_TARGET:
            message = "gradient_target"
            break
        rate = np.exp(X @ parameters[:p] + parameters[p:][day])
        bb, cross, uu, _, _, _ = scoring_information(
            X, aggregation, penalty, precision, day_design, rate, variance_power
        )
        direction, _ = scoring_step(bb, cross, uu, constraints, gradient[:, None])
        direction = direction[:, 0]
        descent = gradient @ direction
        initial_step = 1
        if curvature_scale:
            curvature = directional_curvature(
                X, aggregation, counts, penalty, precision, day, rate, direction, variance_power
            )
            if curvature > 0:
                initial_step = min(1, descent / curvature)
        for line_step in range(MAX_LINE_STEPS):
            step = initial_step * 0.5**line_step
            trial = parameters - step * direction
            trial[p:] = center_daily(trial[p:], years)
            trial_loss, trial_gradient = objective(trial)
            if np.isfinite(trial_loss) and trial_loss <= loss - ARMIJO * step * descent:
                break
        else:
            message = "line_search_limit"
            break
        parameters, loss, gradient = trial, trial_loss, trial_gradient
        history.append(
            dict(
                iteration=iteration,
                loss=loss,
                gradient=abs(gradient).max(),
                step=step,
                initial_step=initial_step,
            )
        )
    return (
        OptimizeResult(
            x=parameters,
            fun=loss,
            jac=gradient,
            nit=len(history) - 1,
            success=abs(gradient).max() < GRADIENT_TARGET,
            message=message,
        ),
        objective,
        history,
    )
