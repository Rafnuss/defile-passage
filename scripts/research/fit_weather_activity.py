"""Fit a two-part hourly weather model: migration occurrence, then positive count size."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from activity_numerics import directional_gradient_check
from scipy.linalg import cholesky, solve_triangular
from scipy.optimize import minimize
from scipy.special import digamma, gammaln

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True, help="Prepared design matrices and masks")
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--keys", nargs="+", help="Optional prepared contexts for a pilot fit")
parser.add_argument("--positive-penalty-multiplier", type=float, default=1)
parser.add_argument(
    "--positive-design", action="store_true", help="Use the simpler positive-only GAM basis"
)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(args.input / "manifest.csv").query("fold < 4")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
hour_results, fit_results = [], []

for record in manifest.itertuples():
    key = record.key
    print(f"{key}: fitting occurrence and positive-count models", flush=True)
    training = pd.read_csv(args.input / f"{key}_train.csv")
    testing = pd.read_csv(args.input / f"{key}_test.csv")
    X = np.loadtxt(args.input / f"{key}_Xtrain.csv", delimiter=",")
    Xt = np.loadtxt(args.input / f"{key}_Xtest.csv", delimiter=",")
    penalty = np.loadtxt(args.input / f"{key}_penalty.csv", delimiter=",")
    positive_penalty = args.positive_penalty_multiplier * penalty
    exposure = training.exposure_hours.to_numpy()
    counts = training["count"].to_numpy()
    beta_start = pd.read_csv(args.input / f"{key}_beta.csv").beta.to_numpy()
    Z, Zt, positive_start = X, Xt, beta_start
    if args.positive_design:
        Z = np.loadtxt(args.input / f"{key}_Ztrain.csv", delimiter=",")
        Zt = np.loadtxt(args.input / f"{key}_Ztest.csv", delimiter=",")
        positive_penalty = np.loadtxt(args.input / f"{key}_positive_penalty.csv", delimiter=",")
        positive_start = pd.read_csv(args.input / f"{key}_positive_beta.csv").beta.to_numpy()

    # Complementary-log-log occurrence scales with real exposure duration.
    def activity_objective(beta):
        hazard = np.exp(np.clip(np.log(exposure) + X @ beta, -30, 30))
        positive = counts > 0
        loss = np.where(positive, -np.log(-np.expm1(-hazard)), hazard).sum()
        ratio = np.divide(
            hazard, np.expm1(np.minimum(hazard, 50)), out=np.zeros_like(hazard), where=hazard > 0
        )
        gradient_eta = np.where(positive, -ratio, hazard)
        return loss + beta @ penalty @ beta / 2, X.T @ gradient_eta + penalty @ beta

    positive_fraction = np.mean(counts > 0)
    lower, upper = -20.0, 20.0
    for _ in range(60):
        shift = (lower + upper) / 2
        probability = -np.expm1(-exposure * np.exp(np.clip(X @ beta_start + shift, -30, 30)))
        if probability.mean() < positive_fraction:
            lower = shift
        else:
            upper = shift
    beta_activity_start = beta_start.copy()
    beta_activity_start[0] += shift
    activity_hazard = exposure * np.exp(np.clip(X @ beta_activity_start, -30, 30))
    activity_weights = np.divide(
        activity_hazard**2,
        np.expm1(np.minimum(activity_hazard, 50)),
        out=np.zeros_like(activity_hazard),
        where=activity_hazard > 0,
    )
    activity_root = cholesky(
        penalty + X.T @ (activity_weights[:, None] * X) + np.eye(X.shape[1]) * 1e-8, lower=True
    )
    activity_transform = solve_triangular(activity_root.T, np.eye(X.shape[1]), lower=False)

    def transformed_activity(parameters):
        beta = beta_activity_start + activity_transform @ parameters
        value, gradient = activity_objective(beta)
        return value, activity_transform.T @ gradient

    activity_fit = minimize(
        transformed_activity,
        np.zeros(X.shape[1]),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 4000, "maxls": 50, "ftol": 1e-13, "gtol": 1e-5},
    )
    if not activity_fit.success:
        raise RuntimeError(
            f"{key} activity: {activity_fit.message}; gradient={np.max(np.abs(activity_fit.jac)):.5g}"
        )

    positive = counts > 0
    X_positive = Z[positive]
    exposure_positive = exposure[positive]
    count_positive = counts[positive]

    # Positive counts follow a zero-truncated NB with shape proportional to exposure.
    def positive_objective(parameters):
        beta, log_kappa = parameters[:-1], parameters[-1]
        kappa = np.exp(log_kappa)
        mu = exposure_positive * np.exp(X_positive @ beta)
        size = kappa * exposure_positive
        log_p0 = -size * np.log1p(mu / size)
        log_nonzero = np.log(-np.expm1(log_p0))
        log_likelihood = (
            gammaln(count_positive + size)
            - gammaln(size)
            - gammaln(count_positive + 1)
            + size * np.log(size)
            + count_positive * np.log(mu)
            - (count_positive + size) * np.log(size + mu)
            - log_nonzero
        )
        score_eta = count_positive - mu * (count_positive + size) / (size + mu)
        ratio = np.exp(log_p0 - log_nonzero)
        score_eta -= ratio * size * mu / (size + mu)
        score_size = (
            digamma(count_positive + size)
            - digamma(size)
            + np.log(size)
            + 1
            - np.log(size + mu)
            - (size + count_positive) / (size + mu)
        )
        dlog_p0 = -np.log1p(mu / size) + mu / (size + mu)
        score_size += ratio * dlog_p0
        gradient = np.r_[X_positive.T @ score_eta, np.sum(size * score_size)]
        value = -log_likelihood.sum() + beta @ positive_penalty @ beta / 2
        gradient[:-1] -= positive_penalty @ beta
        return value, -gradient

    positive_mu = exposure_positive * np.exp(np.clip(X_positive @ positive_start, -30, 30))
    positive_size = max(record.theta, 0.02) * exposure_positive
    positive_weights = positive_mu * positive_size / (positive_mu + positive_size)
    positive_root = cholesky(
        positive_penalty
        + X_positive.T @ (positive_weights[:, None] * X_positive)
        + np.eye(Z.shape[1]) * 1e-8,
        lower=True,
    )
    positive_transform = solve_triangular(positive_root.T, np.eye(Z.shape[1]), lower=False)

    def transformed_positive(parameters):
        physical = np.r_[positive_start + positive_transform @ parameters[:-1], parameters[-1]]
        value, gradient = positive_objective(physical)
        return value, np.r_[positive_transform.T @ gradient[:-1], gradient[-1]]

    positive_fit = minimize(
        transformed_positive,
        np.r_[np.zeros(Z.shape[1]), np.log(max(record.theta, 0.02))],
        jac=True,
        method="L-BFGS-B",
        bounds=[(None, None)] * Z.shape[1] + [(np.log(0.02), np.log(10000))],
        options={"maxiter": 4000, "maxls": 50, "ftol": 1e-13, "gtol": 1e-5},
    )
    positive_restarted = not positive_fit.success
    if positive_restarted:
        positive_fit = minimize(
            transformed_positive,
            positive_fit.x,
            jac=True,
            method="L-BFGS-B",
            bounds=[(None, None)] * Z.shape[1] + [(np.log(0.02), np.log(10000))],
            options={"maxiter": 4000, "maxls": 100, "ftol": 1e-11, "gtol": 1e-5},
        )
    if not positive_fit.success:
        raise RuntimeError(
            f"{key} positive-count: {positive_fit.message}; gradient={np.max(np.abs(positive_fit.jac)):.5g}"
        )

    test_exposure = testing.exposure_hours.to_numpy()
    beta_positive = positive_start + positive_transform @ positive_fit.x[:-1]
    log_kappa = positive_fit.x[-1]
    mu = test_exposure * np.exp(Zt @ beta_positive)
    size = np.exp(log_kappa) * test_exposure
    log_p0 = -size * np.log1p(mu / size)
    beta_activity = beta_activity_start + activity_transform @ activity_fit.x
    active_probability = -np.expm1(-test_exposure * np.exp(Xt @ beta_activity))
    predicted = active_probability * mu / (-np.expm1(log_p0))
    np.savez(
        args.out / f"{key}_activity_fit.npz",
        occurrence_coefficients=beta_activity,
        positive_count_coefficients=beta_positive,
        positive_shape=np.exp(log_kappa),
        occurrence_objective=activity_fit.fun,
        positive_objective=positive_fit.fun,
        positive_penalty_multiplier=args.positive_penalty_multiplier,
    )
    result = testing[
        ["english_name", "date", "year", "start", "end", "exposure_hours", "count", "rain_mm"]
    ].copy()
    result["model"] = "weather_activity"
    result["fold"] = record.fold
    result["gap"] = "hours" if record.fold == 3 else "days"
    result["predicted"] = predicted
    result["active_probability"] = active_probability
    hour_results.append(result)
    fit_results.append(
        dict(
            english_name=record.english_name,
            fold=record.fold,
            activity_gradient=np.max(np.abs(activity_fit.jac)),
            positive_gradient=np.max(np.abs(positive_fit.jac)),
            activity_gradient_check=directional_gradient_check(
                transformed_activity, activity_fit.x
            ),
            positive_gradient_check=directional_gradient_check(
                transformed_positive, positive_fit.x
            ),
            activity_start_gradient_check=directional_gradient_check(
                transformed_activity, np.zeros(X.shape[1])
            ),
            positive_start_gradient_check=directional_gradient_check(
                transformed_positive, np.r_[np.zeros(Z.shape[1]), np.log(max(record.theta, 0.02))]
            ),
            activity_converged=activity_fit.success,
            positive_converged=positive_fit.success,
            activity_message=activity_fit.message,
            positive_message=positive_fit.message,
            activity_iterations=activity_fit.nit,
            positive_iterations=positive_fit.nit,
            positive_restarted=positive_restarted,
            positive_penalty_multiplier=args.positive_penalty_multiplier,
            kappa=np.exp(log_kappa),
            training_positive_fraction=np.mean(counts > 0),
        )
    )

hours = pd.concat(hour_results, ignore_index=True)
hours["rain_exposure"] = hours.rain_mm * hours.exposure_hours
days = hours.groupby(["english_name", "date", "year", "model", "fold", "gap"], as_index=False).agg(
    count=("count", "sum"),
    exposure_hours=("exposure_hours", "sum"),
    predicted=("predicted", "sum"),
    rain_exposure=("rain_exposure", "sum"),
)
days["rain_mm"] = days.pop("rain_exposure") / days.exposure_hours
hours.to_csv(args.out / "activity_held_out_hours.csv", index=False)
days.to_csv(args.out / "activity_held_out_days.csv", index=False)
pd.DataFrame(fit_results).to_csv(args.out / "activity_fit_diagnostics.csv", index=False)
