"""Fit daily Gamma alternatives on the existing hourly weather validation masks.

Run prepare_daily_rate.R first. Population smoothing parameters are estimated by training-only
independent NB GAMs and held fixed for the integrated fits.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_solve, cholesky, solve_triangular
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import nbinom, poisson

from defile_passage.day_rate import (
    MIN_DAILY_RATE,
    N_DRAWS,
    SHAPE_BOUNDS,
    day_precision,
    fit_day_smoothing,
    gamma_nb_posterior,
    nb_day,
    poisson_day,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs/hourly-weather-v3"
MODELS = ("weather_independent", "gamma_day_poisson", "gamma_day_flocks")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--reuse-fits",
    action="store_true",
    help="Reuse saved fits from this unchanged prepared experiment",
)
parser.add_argument("--input", type=Path, default=OUTPUT, help="Prepared matrices and manifest")
parser.add_argument("--out", type=Path, default=OUTPUT)
parser.add_argument("--models", nargs="+", default=MODELS)
parser.add_argument("--keys", nargs="+", help="Optional prepared contexts for inspecting a fit")
args = parser.parse_args()
INPUT = args.input
OUTPUT = args.out
OUTPUT.mkdir(parents=True, exist_ok=True)
MODELS = args.models
rng = np.random.default_rng(20261010)
manifest = pd.read_csv(INPUT / "manifest.csv")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
hour_results, day_results, diagnostics = [], [], []

# Fit each masked population and integrated daily distribution ----------------
for record in manifest.itertuples():
    key = record.key
    training = pd.read_csv(INPUT / f"{key}_train.csv")
    testing = pd.read_csv(INPUT / f"{key}_test.csv")
    X = np.loadtxt(INPUT / f"{key}_Xtrain.csv", delimiter=",")
    Xt = np.loadtxt(INPUT / f"{key}_Xtest.csv", delimiter=",")
    penalty = np.loadtxt(INPUT / f"{key}_penalty.csv", delimiter=",")
    initial = pd.read_csv(INPUT / f"{key}_beta.csv").beta.to_numpy()
    counts = training["count"].to_numpy()
    exposure = training.exposure_hours.to_numpy()
    test_exposure = testing.exposure_hours.to_numpy()
    dates, group = np.unique(training.date, return_inverse=True)
    starts = np.r_[0, np.flatnonzero(np.diff(group)) + 1]
    test_dates, test_group = np.unique(testing.date, return_inverse=True)
    daylight = (
        pd.to_datetime(training.dusk) - pd.to_datetime(training.dawn)
    ).dt.total_seconds().to_numpy() / 3600
    minimum = MIN_DAILY_RATE * exposure / daylight
    for model in MODELS:
        print(f"{key}: {model}", flush=True)
        saved = OUTPUT / f"{key}_{model}.npz"
        if model == "weather_independent":
            beta = initial
            covariance = np.loadtxt(INPUT / f"{key}_V.csv", delimiter=",")
            shape, kappa = np.nan, record.theta
            convergence, gradient, iterations = True, np.nan, 0
            quadrature_error = 0.0
        elif args.reuse_fits and saved.exists():
            result = np.load(saved)
            beta, covariance = result["beta"], result["covariance"]
            shape, kappa = float(result["shape"]), float(result["kappa"])
            convergence = bool(result["convergence"])
            gradient, iterations = float(result["gradient"]), int(result["iterations"])
            quadrature_error = float(result["quadrature_error"])
        elif model == "gamma_day_smoothing":
            smoothing = pd.read_csv(INPUT / f"{key}_smoothing.csv")
            components = np.stack(
                [np.loadtxt(INPUT / f"{key}_S{j}.csv", delimiter=",") for j in smoothing.component]
            )
            physical, penalty, precision, scales, history = fit_day_smoothing(
                np.r_[initial, np.log([1.0, record.theta])],
                X,
                exposure,
                counts,
                starts,
                components,
            )
            beta = physical[:-2]
            shape, kappa = np.exp(physical[-2:])
            corrected = day_precision(
                beta, X, exposure, counts, starts, penalty, shape, kappa, minimum
            )
            covariance = cho_solve((cholesky(corrected, lower=True), True), np.eye(len(beta)))
            convergence, gradient, iterations = (
                True,
                history[-1]["inner_gradient"],
                history[-1]["step"],
            )
            coarse = nb_day(physical, X, exposure, counts, starts, penalty)[0]
            fine = nb_day(physical, X, exposure, counts, starts, penalty, order=121)[0]
            quadrature_error = abs(coarse - fine)
            pd.DataFrame(history).to_csv(OUTPUT / f"{key}_smoothing_trace.csv", index=False)
            smoothing["log_multiplier"] = scales
            smoothing["fitted_sp"] = smoothing.initial_sp * np.exp(scales)
            smoothing.to_csv(OUTPUT / f"{key}_fitted_smoothing.csv", index=False)
            np.savez(
                saved,
                beta=beta,
                covariance=covariance,
                shape=shape,
                kappa=kappa,
                penalty=penalty,
                scales=scales,
                convergence=convergence,
                gradient=gradient,
                iterations=iterations,
                quadrature_error=quadrature_error,
            )
        else:
            objective = poisson_day if model == "gamma_day_poisson" else nb_day
            extra = np.log([1.0]) if model == "gamma_day_poisson" else np.log([1.0, record.theta])
            mu = exposure * np.exp(X @ initial)
            weights = (
                mu if model == "gamma_day_poisson" else mu * record.theta / (mu + record.theta)
            )
            # Precondition the optimizer without changing the objective or penalty.
            root = cholesky(penalty + X.T @ (weights[:, None] * X), lower=True)
            transform = solve_triangular(root.T, np.eye(len(initial)), lower=False)

            def transformed(parameters):
                physical = np.r_[
                    initial + transform @ parameters[: len(initial)], parameters[len(initial) :]
                ]
                value, score = objective(physical, X, exposure, counts, starts, penalty)
                return value, np.r_[transform.T @ score[: len(initial)], score[len(initial) :]]

            fit = minimize(
                transformed,
                np.r_[np.zeros(len(initial)), extra],
                jac=True,
                method="L-BFGS-B",
                bounds=[(None, None)] * len(initial) + [tuple(np.log(SHAPE_BOUNDS))] * len(extra),
                options={"maxiter": 4000, "maxls": 50, "ftol": 1e-12, "gtol": 1e-5},
            )
            beta = initial + transform @ fit.x[: len(initial)]
            shape = np.exp(fit.x[len(initial)])
            kappa = np.nan if model == "gamma_day_poisson" else np.exp(fit.x[-1])
            convergence, iterations = fit.success, fit.nit
            gradient = np.max(np.abs(fit.jac))
            print(
                f"  {fit.message}; iterations={iterations}, gradient={gradient:.5g}, a={shape:.5g}, kappa={kappa:.5g}",
                flush=True,
            )
            if not convergence:
                raise RuntimeError(f"{key} {model}: {fit.message}")
            precision = day_precision(
                beta,
                X,
                exposure,
                counts,
                starts,
                penalty,
                shape,
                None if np.isnan(kappa) else kappa,
                minimum,
            )
            covariance = cho_solve((cholesky(precision, lower=True), True), np.eye(len(beta)))
            quadrature_error = 0.0
            if model == "gamma_day_flocks":
                physical = np.r_[beta, np.log([shape, kappa])]
                coarse = nb_day(physical, X, exposure, counts, starts, penalty)[0]
                fine = nb_day(physical, X, exposure, counts, starts, penalty, order=121)[0]
                quadrature_error = abs(coarse - fine)
            np.savez(
                saved,
                beta=beta,
                covariance=covariance,
                shape=shape,
                kappa=kappa,
                convergence=convergence,
                gradient=gradient,
                iterations=iterations,
                quadrature_error=quadrature_error,
            )
        diagnostics.append(
            dict(
                english_name=record.english_name,
                fold=record.fold,
                model=model,
                day_shape=shape,
                hourly_shape=kappa,
                day_cv=1 / np.sqrt(shape),
                converged=convergence,
                gradient=gradient,
                iterations=iterations,
                quadrature_loglik_difference=quadrature_error,
            )
        )
        if record.fold == 4:
            continue

        # Shared daily draws; remaining hours condition partial gaps only --------
        beta_draws = rng.multivariate_normal(beta, covariance, size=N_DRAWS).T
        rate_draws = test_exposure[:, None] * np.exp(Xt @ beta_draws)
        variance = np.einsum("ij,jk,ik->i", Xt, covariance, Xt)
        expected = test_exposure * np.exp(Xt @ beta + variance / 2)
        expected_mcse = np.zeros(len(testing))
        if model != "weather_independent":
            daily = rng.gamma(shape, 1 / shape, size=(len(test_dates), N_DRAWS))
            conditioned = np.isin(test_dates, dates)
            if conditioned.any():
                retained = np.flatnonzero(np.isin(training.date, test_dates[conditioned]))
                partial_dates, partial_group = np.unique(
                    training.date.to_numpy()[retained], return_inverse=True
                )
                partial_starts = np.r_[0, np.flatnonzero(np.diff(partial_group)) + 1]
                partial_index = np.searchsorted(test_dates, partial_dates)
                train_mu = exposure[retained, None] * np.exp(X[retained] @ beta_draws)
                if model == "gamma_day_poisson":
                    posterior_shape = shape + np.add.reduceat(counts[retained], partial_starts)
                    posterior_rate = shape + np.add.reduceat(train_mu, partial_starts, axis=0)
                    mean_g = posterior_shape[:, None] / posterior_rate
                    daily[partial_index] = rng.gamma(posterior_shape[:, None], 1 / posterior_rate)
                else:
                    mean_g = np.empty((len(partial_dates), N_DRAWS))
                    for draw in range(N_DRAWS):
                        _, z, weights = gamma_nb_posterior(
                            train_mu[:, draw],
                            counts[retained],
                            kappa * exposure[retained],
                            partial_starts,
                            shape,
                        )
                        mean_g[:, draw] = np.sum(weights * np.exp(z), axis=1)
                        selected = (
                            rng.random(len(partial_dates))[:, None] > np.cumsum(weights, axis=1)
                        ).sum(axis=1)
                        daily[partial_index, draw] = np.exp(
                            z[np.arange(len(partial_dates)), selected]
                        )
                hidden = np.flatnonzero(np.isin(test_group, partial_index))
                conditional_means = (
                    rate_draws[hidden] * mean_g[np.searchsorted(partial_index, test_group[hidden])]
                )
                expected[hidden] = conditional_means.mean(axis=1)
                expected_mcse[hidden] = conditional_means.std(axis=1, ddof=1) / np.sqrt(N_DRAWS)
            rate_draws *= daily[test_group]
        if model == "gamma_day_poisson":
            predictive = rng.poisson(rate_draws)
            density = poisson.logpmf(testing["count"].to_numpy()[:, None], rate_draws)
        else:
            size = kappa if model == "weather_independent" else kappa * test_exposure[:, None]
            predictive = rng.negative_binomial(size, size / (size + rate_draws))
            density = nbinom.logpmf(
                testing["count"].to_numpy()[:, None], size, size / (size + rate_draws)
            )
        result = testing[
            ["english_name", "date", "year", "start", "end", "exposure_hours", "count", "rain_mm"]
        ].copy()
        result["model"], result["fold"] = model, record.fold
        result["gap"] = "hours" if record.fold == 3 else "days"
        result["predicted"], result["mean_mcse"] = expected, expected_mcse
        result["log_score"] = logsumexp(density, axis=1) - np.log(N_DRAWS)
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            result[label] = np.quantile(predictive, probability, axis=1)
        hour_results.append(result)
        daily = result.groupby("date", sort=True).agg(
            english_name=("english_name", "first"),
            year=("year", "first"),
            model=("model", "first"),
            fold=("fold", "first"),
            gap=("gap", "first"),
            count=("count", "sum"),
            hours=("exposure_hours", "sum"),
            predicted=("predicted", "sum"),
        )
        daily["rain_mm"] = (result.rain_mm * result.exposure_hours).groupby(
            result.date
        ).sum() / daily.hours
        count_draws = np.zeros((len(test_dates), N_DRAWS))
        np.add.at(count_draws, test_group, predictive)
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            daily[label] = np.quantile(count_draws, probability, axis=1)
        day_results.append(daily.reset_index())
    pd.DataFrame(diagnostics).to_csv(OUTPUT / "diagnostics.csv", index=False)
    pd.concat(hour_results).to_csv(OUTPUT / "held_out_hours.csv", index=False)
    pd.concat(day_results).to_csv(OUTPUT / "held_out_days.csv", index=False)

# Distinguish population calibration from coefficient-uncertainty correction ---
mean_diagnostics = []
for record in manifest.query("fold < 3").itertuples():
    Xt = np.loadtxt(INPUT / f"{record.key}_Xtest.csv", delimiter=",")
    testing = pd.read_csv(INPUT / f"{record.key}_test.csv")
    for model in set(MODELS) - {"weather_independent"}:
        fit = np.load(OUTPUT / f"{record.key}_{model}.npz")
        variance = np.einsum("ij,jk,ik->i", Xt, fit["covariance"], Xt)
        point = testing.exposure_hours * np.exp(Xt @ fit["beta"])
        mean_diagnostics.append(
            dict(
                species=record.english_name,
                model=model,
                fold=record.fold,
                point_total=point.sum(),
                mean_total=np.sum(point * np.exp(variance / 2)),
                max_log_sd=np.sqrt(variance).max(),
                day_shape=float(fit["shape"]),
            )
        )
pd.DataFrame(mean_diagnostics).to_csv(OUTPUT / "mean_diagnostics.csv", index=False)
