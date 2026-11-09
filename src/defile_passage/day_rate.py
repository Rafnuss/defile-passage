"""Research likelihoods for a mean-one Gamma daily migration multiplier.

Rows are sorted by day; ``starts`` contains each day's first row. Smoothing penalties are supplied
by the training-only mgcv population fit. Nothing imports this experiment into the production
export.
"""

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import digamma, gammaln, logsumexp

QUADRATURE_ORDER = 61
LOG_MASS_DROP = 32
MIN_DAILY_RATE = 0.1
N_DRAWS = 500
SHAPE_BOUNDS = (0.02, 10000)


def poisson_day(parameters, X, exposure, counts, starts, penalty):
    """Exact integrated Gamma-Poisson log likelihood and penalized gradient."""
    beta, shape = parameters[:-1], np.exp(parameters[-1])
    mu = exposure * np.exp(X @ beta)
    total = np.add.reduceat(counts, starts)
    mass = np.add.reduceat(mu, starts)
    group = np.repeat(np.arange(len(starts)), np.diff(np.r_[starts, len(counts)]))
    posterior_mean = (shape + total) / (shape + mass)
    likelihood = np.sum(counts * np.log(mu) - gammaln(counts + 1)) + np.sum(
        shape * np.log(shape)
        - gammaln(shape)
        + gammaln(shape + total)
        - (shape + total) * np.log(shape + mass)
    )
    gradient = np.r_[
        X.T @ (counts - mu * posterior_mean[group]) - penalty @ beta,
        shape
        * np.sum(
            np.log(shape)
            + 1
            - digamma(shape)
            + digamma(shape + total)
            - np.log(shape + mass)
            - (shape + total) / (shape + mass)
        ),
    ]
    return -likelihood + beta @ penalty @ beta / 2, -gradient


def gamma_nb_posterior(mu, counts, sizes, starts, shape, order=QUADRATURE_ORDER):
    """Integrate the daily Gamma multiplier with adaptive split Legendre quadrature.

    Integration is in log multiplier, including its Jacobian. Each side of the strictly concave
    mode ends 32 log-density units below the peak. Splitting at the mode resolves narrow peaks and
    the long left tail of small Gamma shapes.
    """
    group = np.repeat(np.arange(len(starts)), np.diff(np.r_[starts, len(counts)]))
    constant = gammaln(counts + sizes) - gammaln(sizes) - gammaln(counts + 1)

    def density(z):
        log_mu = np.log(mu)[:, None] + z[group]
        denominator = np.logaddexp(np.log(sizes)[:, None], log_mu)
        row = (
            constant[:, None]
            + sizes[:, None] * (np.log(sizes)[:, None] - denominator)
            + counts[:, None] * (log_mu - denominator)
        )
        return (
            shape * np.log(shape)
            - gammaln(shape)
            + shape * z
            - shape * np.exp(z)
            + np.add.reduceat(row, starts, axis=0)
        )

    mode = np.log(
        (shape + np.add.reduceat(counts, starts)) / (shape + np.add.reduceat(mu, starts))
    )[:, None]
    for _ in range(40):
        gm = mu[:, None] * np.exp(mode[group])
        first = shape * (1 - np.exp(mode)) + np.add.reduceat(
            sizes[:, None] * (counts[:, None] - gm) / (sizes[:, None] + gm),
            starts,
            axis=0,
        )
        second = -shape * np.exp(mode) - np.add.reduceat(
            sizes[:, None] * (counts + sizes)[:, None] * gm / (sizes[:, None] + gm) ** 2,
            starts,
            axis=0,
        )
        step = np.clip(first / second, -2, 2)
        mode -= step
        if np.max(np.abs(step)) < 1e-10:
            break
    peak = density(mode)
    bounds = []
    for direction in (-1, 1):
        distance = np.ones_like(mode)
        while np.any(density(mode + direction * distance) > peak - LOG_MASS_DROP):
            distance = np.where(
                density(mode + direction * distance) > peak - LOG_MASS_DROP,
                distance * 2,
                distance,
            )
        inside, outside = np.zeros_like(mode), distance
        for _ in range(35):
            middle = (inside + outside) / 2
            below = density(mode + direction * middle) < peak - LOG_MASS_DROP
            outside = np.where(below, middle, outside)
            inside = np.where(below, inside, middle)
        bounds.append(mode + direction * (inside + outside) / 2)
    nodes, weights = leggauss(order)
    left, right = bounds
    z = np.concatenate(
        (left + (mode - left) * (nodes + 1) / 2, mode + (right - mode) * (nodes + 1) / 2),
        axis=1,
    )
    integration_weights = np.concatenate(
        ((mode - left) * weights / 2, (right - mode) * weights / 2), axis=1
    )
    log_mass = density(z) + np.log(integration_weights)
    marginal = logsumexp(log_mass, axis=1)
    posterior = np.exp(log_mass - marginal[:, None])
    return marginal, z, posterior


def nb_day(parameters, X, exposure, counts, starts, penalty, order=QUADRATURE_ORDER):
    """Integrated Gamma-NB likelihood; NB shape is per real hour of exposure."""
    beta = parameters[:-2]
    shape, kappa = np.exp(parameters[-2:])
    mu = exposure * np.exp(X @ beta)
    sizes = kappa * exposure
    group = np.repeat(np.arange(len(starts)), np.diff(np.r_[starts, len(counts)]))
    marginal, z, posterior = gamma_nb_posterior(mu, counts, sizes, starts, shape, order)
    gm = mu[:, None] * np.exp(z[group])
    denominator = sizes[:, None] + gm
    score = sizes[:, None] * (counts[:, None] - gm) / denominator
    mean_score = np.sum(score * posterior[group], axis=1)
    shape_score = shape * np.sum(
        np.log(shape) + 1 - digamma(shape) + np.sum(posterior * (z - np.exp(z)), axis=1)
    )
    kappa_score = np.sum(
        posterior[group]
        * sizes[:, None]
        * (
            digamma((counts + sizes)[:, None])
            - digamma(sizes[:, None])
            + np.log(sizes)[:, None]
            + 1
            - np.log(denominator)
            - (counts + sizes)[:, None] / denominator
        )
    )
    gradient = np.r_[X.T @ mean_score - penalty @ beta, shape_score, kappa_score]
    return -np.sum(marginal) + beta @ penalty @ beta / 2, -gradient


def day_precision(beta, X, exposure, counts, starts, penalty, shape, kappa, minimum):
    """Observed beta information after integration (Louis' identity for NB).

    The small tail floor adds information only; fitted means and counts stay intact. Shapes and the
    smoothing parameters are held at their fitted values.
    """
    mu = exposure * np.exp(X @ beta)
    group = np.repeat(np.arange(len(starts)), np.diff(np.r_[starts, len(counts)]))
    if kappa is None:
        total = np.add.reduceat(counts, starts)
        mass = np.add.reduceat(mu, starts)
        w = mu * ((shape + total) / (shape + mass))[group]
        day_design = np.add.reduceat(X * mu[:, None], starts, axis=0)
        precision = penalty + X.T @ (w[:, None] * X)
        precision -= day_design.T @ (((shape + total) / (shape + mass) ** 2)[:, None] * day_design)
        precision += X.T @ (np.maximum(minimum - mu, 0)[:, None] * X)
    else:
        sizes = kappa * exposure
        _, z, posterior = gamma_nb_posterior(mu, counts, sizes, starts, shape)
        gm = mu[:, None] * np.exp(z[group])
        score = sizes[:, None] * (counts[:, None] - gm) / (sizes[:, None] + gm)
        curvature = sizes[:, None] * (counts + sizes)[:, None] * gm / (sizes[:, None] + gm) ** 2
        w = np.sum(posterior[group] * curvature, axis=1)
        precision = penalty + X.T @ (w[:, None] * X)
        daily_scores = np.stack(
            [np.add.reduceat(X * score[:, j, None], starts, axis=0) for j in range(z.shape[1])],
            axis=1,
        )
        average = np.sum(posterior[:, :, None] * daily_scores, axis=1)
        centered = daily_scores - average[:, None, :]
        precision -= np.einsum("dn,dnp,dnq->pq", posterior, centered, centered, optimize=True)
        extra = np.maximum(minimum - mu, 0) * sizes / (sizes + mu)
        precision += X.T @ (extra[:, None] * X)
    return precision


def smoothing_moments(log_scales, components, beta, covariance, penalized):
    """Gaussian posterior-moment smoothing objective and gradient.

    Components include their initial mgcv scaling. Flat fixed effects are excluded from the prior
    determinant. This is a Laplace-EM update, not exact integration over population coefficients.
    """
    scaled = np.exp(log_scales)[:, None, None] * components
    penalty = scaled.sum(axis=0)
    block = penalty[np.ix_(penalized, penalized)]
    inverse = np.linalg.inv(block)
    moment = np.outer(beta, beta) + covariance
    traces = np.einsum("kij,ji->k", scaled, moment)
    prior_traces = np.einsum("kij,ji->k", scaled[:, penalized][:, :, penalized], inverse)
    value = (traces.sum() - np.linalg.slogdet(block)[1]) / 2
    return value, (traces - prior_traces) / 2


def laplace_score(objective, precision, penalty, penalized):
    """Negative restricted Laplace evidence, up to a fixed basis-dependent constant."""
    return (
        objective
        + (
            2 * np.log(np.diag(np.linalg.cholesky(precision))).sum()
            - 2 * np.log(np.diag(np.linalg.cholesky(penalty[np.ix_(penalized, penalized)]))).sum()
        )
        / 2
    )


SMOOTHING_BOUNDS = (-12, 12)
MAX_SMOOTHING_STEPS = 40
SMOOTHING_TOLERANCE = 0.01
EVIDENCE_TOLERANCE = 1e-4


def fit_nb_population(initial, X, exposure, counts, starts, penalty):
    """Refit coefficients and both count shapes for a specified smoothing penalty."""
    from scipy.linalg import cholesky, solve_triangular
    from scipy.optimize import minimize

    p = X.shape[1]
    mu = exposure * np.exp(X @ initial[:p])
    sizes = np.exp(initial[-1]) * exposure
    weights = mu * sizes / (mu + sizes)
    root = cholesky(penalty + X.T @ (weights[:, None] * X), lower=True)
    transform = solve_triangular(root.T, np.eye(p), lower=False)

    def transformed(parameters):
        physical = np.r_[initial[:p] + transform @ parameters[:p], parameters[p:]]
        value, score = nb_day(physical, X, exposure, counts, starts, penalty)
        return value, np.r_[transform.T @ score[:p], score[p:]]

    fit = minimize(
        transformed,
        np.r_[np.zeros(p), initial[p:]],
        jac=True,
        method="L-BFGS-B",
        bounds=[(None, None)] * p + [tuple(np.log(SHAPE_BOUNDS))] * 2,
        options={"maxiter": 4000, "maxls": 50, "ftol": 1e-10, "gtol": 1e-4},
    )
    if not fit.success and np.max(np.abs(fit.jac)) < 1e-3:
        fit = minimize(
            transformed,
            fit.x,
            jac=True,
            method="L-BFGS-B",
            bounds=[(None, None)] * p + [tuple(np.log(SHAPE_BOUNDS))] * 2,
            options={"maxiter": 4000, "maxls": 100, "ftol": 1e-9, "gtol": 1e-3},
        )
    if not fit.success:
        raise RuntimeError(f"{fit.message}; maximum scaled gradient={np.max(np.abs(fit.jac)):.6g}")
    physical = np.r_[initial[:p] + transform @ fit.x[:p], fit.x[p:]]
    shape, kappa = np.exp(physical[-2:])
    precision = day_precision(
        physical[:p], X, exposure, counts, starts, penalty, shape, kappa, np.zeros(len(counts))
    )
    return physical, fit.fun, precision, np.max(np.abs(fit.jac))


def fit_day_smoothing(initial, X, exposure, counts, starts, components):
    """Alternate integrated count fits with generalized Fellner-Schall smoothing updates.

    Every accepted update must improve restricted Laplace evidence after refitting coefficients and
    both shapes. This uses an approximate smoothing direction; stalled directions and iteration
    limits are reported, not called convergence.
    """
    from scipy.optimize import minimize

    penalized = np.flatnonzero(np.diag(components.sum(axis=0)) > 0)
    scales = np.zeros(len(components))
    penalty = components.sum(axis=0)
    physical, objective, precision, gradient = fit_nb_population(
        initial, X, exposure, counts, starts, penalty
    )
    evidence = laplace_score(objective, precision, penalty, penalized)
    history = [
        dict(step=0, evidence=evidence, change=np.nan, inner_gradient=gradient, status="initial")
    ]
    status = "iteration_limit"
    for step in range(1, MAX_SMOOTHING_STEPS + 1):
        covariance = np.linalg.inv(precision)
        update = minimize(
            smoothing_moments,
            scales,
            args=(components, physical[:-2], covariance, penalized),
            jac=True,
            method="L-BFGS-B",
            bounds=[SMOOTHING_BOUNDS] * len(scales),
            options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-6},
        )
        scaled = np.exp(scales)[:, None, None] * components
        prior_inverse = np.linalg.inv(penalty[np.ix_(penalized, penalized)])
        numerator = np.einsum(
            "kij,ji->k", scaled[:, penalized][:, :, penalized], prior_inverse
        ) - np.einsum("kij,ji->k", scaled, covariance)
        denominator = np.einsum("i,kij,j->k", physical[:-2], scaled, physical[:-2])
        # Non-concave observed information can invalidate the Schall direction;
        # retain the positive posterior-moment proposal for those components.
        proposal = update.x.copy()
        regular = (numerator > 0) & (denominator > 0)
        proposal[regular] = np.clip(
            scales[regular] + np.log(numerator[regular] / denominator[regular]), *SMOOTHING_BOUNDS
        )
        direction = proposal - scales
        if np.max(np.abs(direction)) < SMOOTHING_TOLERANCE:
            status = "moment_converged"
            break
        accepted = False
        for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
            proposed_scales = scales + fraction * direction
            proposed_penalty = np.einsum("k,kij->ij", np.exp(proposed_scales), components)
            try:
                proposed, value, information, proposed_gradient = fit_nb_population(
                    physical, X, exposure, counts, starts, proposed_penalty
                )
            except RuntimeError:
                continue
            score = laplace_score(value, information, proposed_penalty, penalized)
            if score < evidence:
                accepted = True
                change = evidence - score
                physical, objective, precision, gradient = (
                    proposed,
                    value,
                    information,
                    proposed_gradient,
                )
                scales, penalty, evidence = proposed_scales, proposed_penalty, score
                history.append(
                    dict(
                        step=step,
                        evidence=evidence,
                        change=change,
                        inner_gradient=gradient,
                        status="accepted",
                    )
                )
                print(
                    f"    smoothing step {step}: evidence={score:.5f}, improvement={change:.5g}",
                    flush=True,
                )
                break
        if accepted and change < EVIDENCE_TOLERANCE:
            status = "evidence_plateau"
            break
        if not accepted:
            status = "direction_stalled"
            break
    history.append(
        dict(step=step, evidence=evidence, change=0.0, inner_gradient=gradient, status=status)
    )
    return physical, penalty, precision, scales, history
