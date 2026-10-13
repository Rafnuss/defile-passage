"""Fit a hurdle count model with one Gamma migration state shared across each survey day."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from activity_numerics import directional_gradient_check
from adaptive_daily_integration import adaptive_hurdle_rule
from gamma_count_moments import gamma_hour_moments
from scipy.linalg import block_diag, cholesky, solve_triangular
from scipy.optimize import minimize
from scipy.special import digamma, gammaln, logsumexp
from shared_activity_prediction import gamma_quadrature, joint_count_draws

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--input", type=Path, required=True, help="Prepared matrices and validation folds"
)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--keys", nargs="+", help="Optional contexts for fitting a small pilot")
parser.add_argument(
    "--year-folds", action="store_true", help="Use folds 5+ from leave-one-year-out preparation"
)
parser.add_argument("--quadrature-order", type=int, default=61)
parser.add_argument(
    "--draws", type=int, default=0, help="Joint coefficient/day/count predictive draws"
)
parser.add_argument(
    "--adaptive", action="store_true", help="Posterior-centered log-Gamma quadrature"
)
parser.add_argument(
    "--positive-pooling",
    type=float,
    default=0,
    help="Pseudo-observation strength shrinking positive log rates toward their species baseline",
)
parser.add_argument("--warm-start", type=Path, help="Saved matching fits for initialization")
parser.add_argument(
    "--resume",
    action="store_true",
    help="Reuse completed context outputs with identical run settings",
)
parser.add_argument(
    "--full-reference",
    action="store_true",
    help="Fit fold 4 using all recent training data; not validation",
)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(args.input / "manifest.csv")
manifest = manifest.query(
    "fold == 4" if args.full_reference else ("fold >= 5" if args.year_folds else "fold < 4")
)
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
hour_results, fit_results = [], []
quadrature_order = args.quadrature_order

for record in manifest.itertuples():
    key = record.key
    if args.resume and (args.out / f"{key}_hours.csv").exists():
        hour_results.append(pd.read_csv(args.out / f"{key}_hours.csv"))
        fit_results.append(pd.read_csv(args.out / f"{key}_diagnostics.csv").iloc[0].to_dict())
        continue
    print(f"{key}: fitting shared daily occurrence and positive-count model", flush=True)
    training = pd.read_csv(args.input / f"{key}_train.csv")
    testing = pd.read_csv(args.input / f"{key}_test.csv")
    X = np.loadtxt(args.input / f"{key}_Xtrain.csv", delimiter=",")
    Xt = np.loadtxt(args.input / f"{key}_Xtest.csv", delimiter=",")
    penalty = np.loadtxt(args.input / f"{key}_penalty.csv", delimiter=",")
    centered = X - np.average(X, axis=0, weights=training.exposure_hours)
    positive_penalty = (
        penalty
        + args.positive_pooling
        * centered.T
        @ (training.exposure_hours.to_numpy()[:, None] * centered)
        / training.exposure_hours.sum()
    )
    counts = training["count"].to_numpy()
    exposure = training.exposure_hours.to_numpy()
    day_values, day_group = np.unique(training.date, return_inverse=True)
    day_rows = [np.flatnonzero(day_group == i) for i in range(len(day_values))]
    reference = np.load(args.input / f"{key}_gamma_day_flocks.npz")
    shape = float(reference["shape"])
    beta_start = reference["beta"]
    kappa_start = float(reference["kappa"])

    g_nodes, log_prior_weights = gamma_quadrature(shape, quadrature_order)
    # Initialize the occurrence rate to the observed positive-hour frequency.
    fraction = np.mean(counts > 0)
    lower, upper = -20.0, 20.0
    for _ in range(60):
        shift = (lower + upper) / 2
        p = -np.expm1(-exposure * np.exp(np.clip(X @ beta_start + shift, -30, 30)))
        if p.mean() < fraction:
            lower = shift
        else:
            upper = shift
    alpha_start = beta_start.copy()
    alpha_start[0] += shift
    h_start = exposure * np.exp(np.clip(X @ alpha_start, -30, 30))
    alpha_weights = h_start**2 / np.expm1(np.minimum(h_start, 50))
    alpha_transform = solve_triangular(
        cholesky(
            penalty + X.T @ (alpha_weights[:, None] * X) + np.eye(X.shape[1]) * 1e-8, lower=True
        ).T,
        np.eye(X.shape[1]),
        lower=False,
    )
    positive = counts > 0
    X_positive = X[positive]
    positive_mu = exposure[positive] * np.exp(np.clip(X_positive @ beta_start, -30, 30))
    positive_size = kappa_start * exposure[positive]
    beta_weights = positive_mu * positive_size / (positive_mu + positive_size)
    beta_transform = solve_triangular(
        cholesky(
            positive_penalty
            + X_positive.T @ (beta_weights[:, None] * X_positive)
            + np.eye(X.shape[1]) * 1e-8,
            lower=True,
        ).T,
        np.eye(X.shape[1]),
        lower=False,
    )

    def day_rule(rows, alpha, beta, log_kappa):
        if not args.adaptive:
            return g_nodes, log_prior_weights
        e = exposure[rows]
        return adaptive_hurdle_rule(
            shape,
            counts[rows],
            e * np.exp(np.clip(X[rows] @ alpha, -30, 30)),
            e * np.exp(np.clip(X[rows] @ beta, -30, 30)),
            np.exp(log_kappa) * e,
            quadrature_order,
        )

    def conditional_rows(rows, alpha, beta, log_kappa, nodes=None):
        if nodes is None:
            nodes = g_nodes
        y = counts[rows]
        e = exposure[rows]
        design = X[rows]
        h = e * np.exp(np.clip(design @ alpha, -30, 30))
        mu = e * np.exp(np.clip(design @ beta, -30, 30))
        size = np.exp(log_kappa) * e
        gh = h[:, None] * nodes[None, :]
        gm = mu[:, None] * nodes[None, :]
        zero = y == 0
        log_likelihood = np.where(zero[:, None], -gh, np.log(-np.expm1(-gh)))
        score_alpha = np.where(
            zero[:, None], -gh, np.where(gh < 50, gh / np.expm1(np.minimum(gh, 50)), 0)
        )
        score_beta = np.zeros_like(gm)
        score_kappa = np.zeros_like(gm)
        if (~zero).any():
            yp = y[~zero, None]
            mup = gm[~zero]
            sp = size[~zero, None]
            log_p0 = -sp * np.log1p(mup / sp)
            log_nonzero = np.log(-np.expm1(log_p0))
            log_nb = (
                gammaln(yp + sp)
                - gammaln(sp)
                - gammaln(yp + 1)
                + sp * np.log(sp)
                + yp * np.log(mup)
                - (yp + sp) * np.log(sp + mup)
            )
            log_likelihood[~zero] += log_nb - log_nonzero
            ratio = np.exp(log_p0 - log_nonzero)
            score_mean = yp - mup * (yp + sp) / (sp + mup)
            score_mean -= ratio * sp * mup / (sp + mup)
            score_beta[~zero] = score_mean
            score_size = (
                digamma(yp + sp)
                - digamma(sp)
                + np.log(sp)
                + 1
                - np.log(sp + mup)
                - (sp + yp) / (sp + mup)
            )
            dlog_p0 = -np.log1p(mup / sp) + mup / (sp + mup)
            score_kappa[~zero] = ratio * dlog_p0 + score_size
            score_kappa[~zero] *= sp
        return log_likelihood, score_alpha, score_beta, score_kappa

    def objective(parameters):
        n = X.shape[1]
        alpha = alpha_start + alpha_transform @ parameters[:n]
        beta = beta_start + beta_transform @ parameters[n : 2 * n]
        log_kappa = parameters[-1]
        value = 0.0
        grad_alpha = np.zeros(n)
        grad_beta = np.zeros(n)
        grad_kappa = 0.0
        for rows in day_rows:
            if not counts[rows].any():
                hazard = exposure[rows] * np.exp(np.clip(X[rows] @ alpha, -30, 30))
                value += shape * np.log1p(hazard.sum() / shape)
                grad_alpha += X[rows].T @ hazard * shape / (shape + hazard.sum())
                continue
            nodes, weights = day_rule(rows, alpha, beta, log_kappa)
            log_likelihood, score_alpha, score_beta, score_kappa = conditional_rows(
                rows, alpha, beta, log_kappa, nodes
            )
            log_joint = weights + log_likelihood.sum(axis=0)
            log_marginal = logsumexp(log_joint)
            posterior = np.exp(log_joint - log_marginal)
            value -= log_marginal
            grad_alpha -= X[rows].T @ (score_alpha @ posterior)
            grad_beta -= X[rows].T @ (score_beta @ posterior)
            grad_kappa -= np.sum(score_kappa @ posterior)
        value += (alpha @ penalty @ alpha + beta @ positive_penalty @ beta) / 2
        grad_alpha += penalty @ alpha
        grad_beta += positive_penalty @ beta
        gradient = np.r_[
            alpha_transform.T @ grad_alpha,
            beta_transform.T @ grad_beta,
            grad_kappa,
        ]
        return value, gradient

    initial = np.r_[np.zeros(2 * X.shape[1]), np.log(kappa_start)]
    if args.warm_start:
        previous = np.load(args.warm_start / f"{key}_shared_activity_fit.npz")
        initial = np.r_[
            np.linalg.solve(alpha_transform, previous["occurrence_coefficients"] - alpha_start),
            np.linalg.solve(beta_transform, previous["positive_count_coefficients"] - beta_start),
            np.log(previous["positive_shape"]),
        ]
    fit = minimize(
        objective,
        initial,
        jac=True,
        method="L-BFGS-B",
        bounds=[(None, None)] * (2 * X.shape[1]) + [(np.log(0.02), np.log(10000))],
        options={"maxiter": 2500, "maxls": 40, "ftol": 1e-13, "gtol": 1e-5},
    )
    if not fit.success:
        fit = minimize(
            objective,
            fit.x,
            jac=True,
            method="L-BFGS-B",
            bounds=[(None, None)] * (2 * X.shape[1]) + [(np.log(0.02), np.log(10000))],
            options={"maxiter": 2500, "maxls": 100, "ftol": 1e-12, "gtol": 1e-5},
        )
    if not fit.success:
        raise RuntimeError(f"{key}: {fit.message}; maximum gradient={np.max(np.abs(fit.jac)):.5g}")
    n = X.shape[1]
    alpha = alpha_start + alpha_transform @ fit.x[:n]
    beta = beta_start + beta_transform @ fit.x[n : 2 * n]
    kappa = np.exp(fit.x[-1])
    original_nodes, original_weights = g_nodes, log_prior_weights
    quadrature_order = 2 * args.quadrature_order + 1
    g_nodes, log_prior_weights = gamma_quadrature(shape, quadrature_order)
    refined_value, refined_gradient = objective(fit.x)
    quadrature_loss_delta = abs(refined_value - fit.fun) / len(day_rows)
    quadrature_gradient_delta = np.max(np.abs(refined_gradient - fit.jac))
    g_nodes, log_prior_weights = original_nodes, original_weights
    quadrature_order = args.quadrature_order

    # Marginal coefficient information uses the posterior covariance of day scores.
    information = block_diag(penalty, positive_penalty)
    for rows in day_rows:
        if not counts[rows].any():
            hazard = exposure[rows] * np.exp(np.clip(X[rows] @ alpha, -30, 30))
            score = X[rows].T @ hazard
            information[:n, :n] += shape / (shape + hazard.sum()) * X[rows].T @ (
                hazard[:, None] * X[rows]
            ) - shape / (shape + hazard.sum()) ** 2 * np.outer(score, score)
            continue
        nodes, weights = day_rule(rows, alpha, beta, np.log(kappa))
        log_likelihood, score_alpha, score_beta, _ = conditional_rows(
            rows, alpha, beta, np.log(kappa), nodes
        )
        log_weights = weights + log_likelihood.sum(axis=0)
        posterior = np.exp(log_weights - logsumexp(log_weights))
        gh = exposure[rows, None] * np.exp(np.clip(X[rows] @ alpha, -30, 30))[:, None] * nodes
        gm = exposure[rows, None] * np.exp(np.clip(X[rows] @ beta, -30, 30))[:, None] * nodes
        size = kappa * exposure[rows, None]
        zero = counts[rows] == 0
        second_alpha = np.where(zero[:, None], -gh, score_alpha * (1 - gh - score_alpha))
        log_p0 = -size * np.log1p(gm / size)
        ratio = np.exp(log_p0) / (-np.expm1(log_p0))
        a = size * gm / (size + gm)
        second_beta = (
            -gm * size * (counts[rows, None] + size) / (size + gm) ** 2
            + ratio * (1 + ratio) * a**2
            - ratio * size**2 * gm / (size + gm) ** 2
        )
        second_beta[zero] = 0
        information[:n, :n] -= X[rows].T @ ((second_alpha @ posterior)[:, None] * X[rows])
        information[n:, n:] -= X[rows].T @ ((second_beta @ posterior)[:, None] * X[rows])
        scores = np.vstack([X[rows].T @ score_alpha, X[rows].T @ score_beta])
        mean_score = scores @ posterior
        information -= (scores * posterior) @ scores.T - np.outer(mean_score, mean_score)
    transform = block_diag(alpha_transform, beta_transform)
    transformed_information = transform.T @ information @ transform
    transformed_information = (transformed_information + transformed_information.T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(transformed_information)
    floor = max(eigenvalues.max() * 1e-8, 1e-8)
    covariance = (
        transform
        @ ((eigenvectors / np.maximum(eigenvalues, floor)) @ eigenvectors.T)
        @ transform.T
    )
    directions = np.random.default_rng(20261011).normal(size=(4, 2 * n))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    hessian_errors = []
    for direction in directions:
        perturbation = np.r_[direction, 0] * 1e-4
        numerical = (
            objective(fit.x + perturbation)[1][:-1] - objective(fit.x - perturbation)[1][:-1]
        ) / 2e-4
        hessian_errors.append(
            np.max(np.abs(transformed_information @ direction - numerical))
            / max(1, np.max(np.abs(numerical)))
        )

    # Condition the shared daily state on any retained hours, then predict hidden intervals.
    train_dates = pd.to_datetime(training.date).to_numpy()
    test_dates = pd.to_datetime(testing.date).to_numpy()
    test_exposure = testing.exposure_hours.to_numpy()
    h_test = test_exposure * np.exp(np.clip(Xt @ alpha, -30, 30))
    mu_test = test_exposure * np.exp(np.clip(Xt @ beta, -30, 30))
    size_test = kappa * test_exposure
    activity_probability = np.empty(len(testing))
    predicted = np.empty(len(testing))
    for date in np.unique(test_dates):
        test_index = np.flatnonzero(test_dates == date)
        train_index = np.flatnonzero(train_dates == date)
        prediction_nodes, prediction_weights = gamma_quadrature(shape, max(121, quadrature_order))
        posterior = np.exp(prediction_weights)
        if len(train_index) and not counts[train_index].any():
            retained_hazard = exposure[train_index] * np.exp(
                np.clip(X[train_index] @ alpha, -30, 30)
            )
            prediction_nodes = prediction_nodes * shape / (shape + retained_hazard.sum())
        elif len(train_index):
            prediction_nodes, weights = day_rule(train_index, alpha, beta, np.log(kappa))
            log_likelihood, _, _, _ = conditional_rows(
                train_index, alpha, beta, np.log(kappa), prediction_nodes
            )
            log_weights = weights + log_likelihood.sum(axis=0)
            posterior = np.exp(log_weights - logsumexp(log_weights))
        gh = h_test[test_index, None] * prediction_nodes[None, :]
        gm = mu_test[test_index, None] * prediction_nodes[None, :]
        size = size_test[test_index, None]
        log_p0 = -size * np.log1p(gm / size)
        probability = -np.expm1(-gh)
        positive_mean = gm / (-np.expm1(log_p0))
        activity_probability[test_index] = probability @ posterior
        predicted[test_index] = (probability * positive_mean) @ posterior
        if not len(train_index) or not counts[train_index].any():
            rate = shape + (retained_hazard.sum() if len(train_index) else 0)
            means, active = gamma_hour_moments(
                shape, rate, h_test[test_index], mu_test[test_index], size_test[test_index]
            )
            predicted[test_index], activity_probability[test_index] = means, active

    result = testing[
        ["english_name", "date", "year", "start", "end", "exposure_hours", "count", "rain_mm"]
    ].copy()
    result["model"] = "shared_weather_activity"
    result["fold"] = record.fold
    result["gap"] = "hours" if record.fold == 3 else "days"
    result["predicted"] = predicted
    result["active_probability"] = activity_probability
    result["daily_shape"] = shape
    if args.draws:
        rng = np.random.default_rng(
            20261011 + int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        )
        count_draws, expected_draws, log_score, predictive_activity = joint_count_draws(
            training,
            testing,
            X,
            Xt,
            alpha,
            beta,
            covariance,
            shape,
            kappa,
            g_nodes,
            log_prior_weights,
            args.draws,
            rng,
            adaptive=args.adaptive,
            adaptive_order=quadrature_order,
        )
        result["predictive_mean"] = expected_draws.mean(axis=1)
        result["mean_mcse"] = expected_draws.std(axis=1) / np.sqrt(args.draws)
        result["log_score"] = log_score
        result["predictive_active_probability"] = predictive_activity
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            result[label] = np.quantile(count_draws, probability, axis=1)
        dates, date_group = np.unique(testing.date, return_inverse=True)
        daily_draws = np.zeros((len(dates), args.draws))
        np.add.at(daily_draws, date_group, count_draws)
        np.savez_compressed(
            args.out / f"{key}_predictive_draws.npz",
            hourly_counts=count_draws,
            daily_counts=daily_draws,
            dates=dates.astype(str),
            date_group=date_group,
        )
    hour_results.append(result)
    fit_results.append(
        dict(
            english_name=record.english_name,
            fold=record.fold,
            converged=fit.success,
            message=fit.message,
            iterations=fit.nit,
            gradient=np.max(np.abs(fit.jac)),
            gradient_check=directional_gradient_check(objective, fit.x),
            start_gradient_check=directional_gradient_check(objective, initial),
            daily_shape_fixed=shape,
            positive_shape=kappa,
            quadrature_order=quadrature_order,
            adaptive=args.adaptive,
            positive_pooling=args.positive_pooling,
            information_min_eigenvalue=eigenvalues.min(),
            information_regularized_modes=int((eigenvalues < floor).sum()),
            hessian_check=max(hessian_errors),
            predictive_draws=args.draws,
            quadrature_loss_delta_per_day=quadrature_loss_delta,
            quadrature_gradient_delta=quadrature_gradient_delta,
        )
    )
    np.savez(
        args.out / f"{key}_shared_activity_fit.npz",
        occurrence_coefficients=alpha,
        positive_count_coefficients=beta,
        daily_shape=shape,
        positive_shape=kappa,
        quadrature_nodes=g_nodes,
        quadrature_log_weights=log_prior_weights,
        coefficient_covariance=covariance,
        coefficient_information=information,
    )
    result.to_csv(args.out / f"{key}_hours.csv", index=False)
    pd.DataFrame([fit_results[-1]]).to_csv(args.out / f"{key}_diagnostics.csv", index=False)
    pd.DataFrame(fit_results).to_csv(args.out / "shared_activity_fit_diagnostics.csv", index=False)

hours = pd.concat(hour_results, ignore_index=True)
hours["rain_exposure"] = hours.rain_mm * hours.exposure_hours
days = hours.groupby(["english_name", "date", "year", "model", "fold", "gap"], as_index=False).agg(
    count=("count", "sum"),
    exposure_hours=("exposure_hours", "sum"),
    predicted=("predicted", "sum"),
    rain_exposure=("rain_exposure", "sum"),
)
days["rain_mm"] = days.pop("rain_exposure") / days.exposure_hours
if args.draws:
    for record in manifest.itertuples():
        draws = np.load(args.out / f"{record.key}_predictive_draws.npz")
        index = days.english_name.eq(record.english_name) & days.fold.eq(record.fold)
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            quantiles = pd.Series(
                np.quantile(draws["daily_counts"], probability, axis=1), index=draws["dates"]
            )
            days.loc[index, label] = days.loc[index, "date"].map(quantiles)
hours.to_csv(args.out / "shared_activity_held_out_hours.csv", index=False)
days.to_csv(args.out / "shared_activity_held_out_days.csv", index=False)
