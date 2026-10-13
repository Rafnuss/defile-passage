"""Fit intact mixed-scale counts with shared daily activity and hourly weather.

The calibration candidate estimates intercept/rain corrections. --refit-time also estimates
both GAM time smooths, conditional on other training GAM effects, smoothing, shape and size.
--draws 0 fits and checks point predictions without computing predictive uncertainty.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from activity_numerics import directional_gradient_check
from adaptive_daily_integration import adaptive_gamma_rule
from coherent_hour_counts import thinned_hour_logpmf, tilted_coarse_probability
from gamma_count_moments import gamma_hour_moments, gamma_interval_active
from scipy.linalg import block_diag, cholesky, solve_triangular
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import nbinom
from shared_activity_prediction import gamma_quadrature

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--prepared", type=Path, required=True)
parser.add_argument("--warm-start", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--keys", nargs="+")
parser.add_argument("--order", type=int, default=31)
parser.add_argument("--draws", type=int, default=300)
parser.add_argument("--refit-time", action="store_true")
parser.add_argument("--extended-time", action="store_true")
parser.add_argument("--positive-pooling", type=float, default=24)
parser.add_argument("--restart", action="store_true")
parser.add_argument(
    "--resume", action="store_true", help="Reuse completed contexts with identical settings"
)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(args.input / "manifest.csv")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
results, diagnostics = [], []
for context in manifest.itertuples():
    key = context.key
    if args.resume and (args.out / f"{key}_diagnostics.csv").exists():
        results.append(pd.read_csv(args.out / f"{key}_predictions.csv"))
        diagnostics.append(pd.read_csv(args.out / f"{key}_diagnostics.csv").iloc[0].to_dict())
        continue
    print(f"{key}: fitting intact counts under canonical-hour thinning", flush=True)
    observations = pd.read_csv(args.input / f"{key}_observations.csv")
    components = pd.read_csv(args.input / f"{key}_components.csv")
    X = np.loadtxt(args.input / f"{key}_X.csv", delimiter=",")
    warm = np.load(args.warm_start / f"{key}_shared_activity_fit.npz")
    shape, size = float(warm["daily_shape"]), float(warm["positive_shape"])
    gate_base, count_base = (
        X @ warm["occurrence_coefficients"],
        X @ warm["positive_count_coefficients"],
    )
    original_gate, original_count = gate_base.copy(), count_base.copy()
    Z = np.column_stack([np.ones(len(components)), np.log1p(components.rain_mm)])
    n = 2
    initial = np.zeros(4)
    penalty_gate = penalty_count = np.eye(2)
    linear_count = np.zeros(2)
    q = components.fraction.to_numpy()
    mapping = {
        i: np.flatnonzero(components.observation_id.eq(i)) for i in observations.observation_id
    }
    year = pd.to_datetime(observations.date).dt.year
    heldout_year = (
        pd.read_csv(args.prepared / "manifest.csv").set_index("key").loc[key, "heldout_year"]
        if context.fold >= 5
        else None
    )
    hidden = (
        year.eq(heldout_year) if context.fold >= 5 else pd.Series(False, index=observations.index)
    )
    training, testing = observations[~hidden], observations[hidden]
    if args.refit_time:
        names = pd.read_csv(args.input / f"{key}_coefficient_names.csv")
        indices = names.loc[names.time_effect, "index"].to_numpy()
        old_time = X[:, indices]
        gate_base -= old_time @ warm["occurrence_coefficients"][indices]
        count_base -= old_time @ warm["positive_count_coefficients"][indices]
        time_design = (
            np.loadtxt(args.input / f"{key}_time_X.csv", delimiter=",")
            if args.extended_time
            else old_time
        )
        Z = np.column_stack([Z, time_design])
        n = Z.shape[1]
        train_rows = np.flatnonzero(components.observation_id.isin(training.observation_id))
        if args.extended_time:
            initial = np.zeros(2 * n)
            time_penalty = np.loadtxt(args.input / f"{key}_time_penalty.csv", delimiter=",")
        else:
            initial = np.r_[
                np.zeros(2),
                warm["occurrence_coefficients"][indices],
                np.zeros(2),
                warm["positive_count_coefficients"][indices],
            ]
            smoothing = np.loadtxt(args.input / f"{key}_penalty.csv", delimiter=",")
            time_penalty = smoothing[np.ix_(indices, indices)]
        penalty_gate = np.zeros((n, n))
        penalty_gate[:2, :2] = np.eye(2)
        penalty_gate[2:, 2:] = time_penalty
        exposure = q[train_rows]
        centered = Z[train_rows] - np.average(Z[train_rows], axis=0, weights=exposure)
        penalty_count = (
            penalty_gate
            + args.positive_pooling * centered.T @ (exposure[:, None] * centered) / exposure.sum()
        )
        offset_centered = count_base[train_rows] - np.average(
            count_base[train_rows], weights=exposure
        )
        linear_count = (
            args.positive_pooling * centered.T @ (exposure * offset_centered) / exposure.sum()
        )
    assert not components.groupby("slot_start").observation_id.nunique().gt(1).any()
    dates = [group for _, group in training.groupby("date")]
    order = args.order
    zero_rule = {
        n: gamma_quadrature(shape, max(121, 4 * n + 1)) for n in [args.order, 2 * args.order + 1]
    }

    structures = {}
    for group in dates:
        single, counts_single, coarse = [], [], []
        for observation in group.itertuples():
            rows = mapping[observation.observation_id]
            if len(rows) == 1 or observation.count == 0:
                single.extend(rows)
                counts_single.extend([observation.count] * len(rows))
            else:
                coarse.append((rows, int(observation.count)))
        structures[id(group)] = (np.array(single, dtype=int), np.array(counts_single), coarse)

    def conditional(group, nodes, parameters, scores=False):
        rows, y, coarse = structures[id(group)]
        hazard = np.exp(np.clip(gate_base[rows] + Z[rows] @ parameters[:n], -30, 30))
        mean = np.exp(np.clip(count_base[rows] + Z[rows] @ parameters[n:], -30, 30))
        values, dh, dm = thinned_hour_logpmf(
            y[:, None], hazard[:, None], mean[:, None], size, q[rows, None], nodes
        )
        log_likelihood = values.sum(axis=0)
        gradient = np.vstack([Z[rows].T @ dh, Z[rows].T @ dm])
        for rows, count in coarse:
            hazard = np.exp(np.clip(gate_base[rows] + Z[rows] @ parameters[:n], -30, 30))
            mean = np.exp(np.clip(count_base[rows] + Z[rows] @ parameters[n:], -30, 30))
            for j, state in enumerate(nodes):
                values = tilted_coarse_probability(
                    count, hazard, mean, np.full(len(rows), size), q[rows], state, scores=scores
                )
                if scores:
                    value, dh, dm = values
                    log_likelihood[j] += value
                    gradient[:n, j] += Z[rows].T @ dh
                    gradient[n:, j] += Z[rows].T @ dm
                else:
                    log_likelihood[j] += values
        return log_likelihood, gradient

    def objective(parameters):
        loss = (
            parameters[:n] @ penalty_gate @ parameters[:n]
            + parameters[n:] @ penalty_count @ parameters[n:]
        ) / 2 + linear_count @ parameters[n:]
        gradient = np.r_[
            penalty_gate @ parameters[:n], penalty_count @ parameters[n:] + linear_count
        ]
        for group in dates:
            if not group["count"].any():
                rows = np.concatenate([mapping[i] for i in group.observation_id])
                hazard = np.exp(np.clip(gate_base[rows] + Z[rows] @ parameters[:n], -30, 30))
                proposal_rate = shape + np.sum(q[rows] * hazard)
                unit_nodes, weights = zero_rule[order]
                nodes = unit_nodes * shape / proposal_rate
                weights = (
                    weights
                    + shape * np.log(shape / proposal_rate)
                    + (proposal_rate - shape) * nodes
                )
            else:
                nodes, weights = adaptive_gamma_rule(
                    shape, lambda nodes: conditional(group, nodes, parameters)[0], order
                )
            likelihood, scores = conditional(group, nodes, parameters, scores=True)
            joint = weights + likelihood
            value = logsumexp(joint)
            posterior = np.exp(joint - value)
            loss -= value
            gradient -= scores @ posterior
        return loss, gradient

    if args.refit_time:
        gram = Z[train_rows].T @ (q[train_rows, None] * Z[train_rows])
        scale = block_diag(
            cholesky(penalty_gate + 0.25 * gram, lower=True),
            cholesky(penalty_count + 0.25 * gram, lower=True),
        )

        tolerance = 1e-4 / np.abs(scale).sum(axis=1).max()
        if args.restart:
            initial = np.load(args.out / f"{key}_optimization_checkpoint.npz")["parameters"]

        def scaled_objective(parameters):
            value, gradient = objective(solve_triangular(scale.T, parameters, lower=False))
            return value, solve_triangular(scale, gradient, lower=True)

        fit = minimize(
            scaled_objective,
            scale.T @ initial,
            jac=True,
            method="BFGS",
            options={"gtol": tolerance, "maxiter": 500},
        )
        if not fit.success and np.max(abs(fit.jac)) > tolerance:
            fit = minimize(
                scaled_objective,
                fit.x,
                jac=True,
                method="L-BFGS-B",
                options={"gtol": tolerance/10, "ftol": 1e-15, "maxiter": 1000, "maxls": 100},
            )
        fit.x = solve_triangular(scale.T, fit.x, lower=False)
        fit.fun, fit.jac = objective(fit.x)
    else:
        fit = minimize(
            objective, initial, jac=True, method="BFGS", options={"gtol": 1e-5, "maxiter": 300}
        )
        if not fit.success and np.max(abs(fit.jac)) > 1e-4:
            fit = minimize(
                objective,
                fit.x,
                jac=True,
                method="L-BFGS-B",
                options={"gtol": 1e-6, "ftol": 1e-12, "maxiter": 300, "maxls": 80},
            )
    gradient_check = directional_gradient_check(objective, fit.x)
    order = 2 * args.order + 1
    refined_value, refined_gradient = objective(fit.x)
    order = args.order
    zero_rule = {
        n: gamma_quadrature(shape, max(121, 4 * n + 1)) for n in [args.order, 2 * args.order + 1]
    }
    information = covariance = np.zeros((2 * n, 2 * n))
    if args.draws:
        information = np.column_stack(
            [
                (
                    objective(fit.x + np.eye(2 * n)[i] * 1e-4)[1]
                    - objective(fit.x - np.eye(2 * n)[i] * 1e-4)[1]
                )
                / 2e-4
                for i in range(2 * n)
            ]
        )
        information = (information + information.T) / 2
        assert np.linalg.eigvalsh(information).min() > 0
        covariance = np.linalg.inv(information)
    np.savez(args.out / f"{key}_optimization_checkpoint.npz", parameters=fit.x, gradient=fit.jac, gradient_check=gradient_check, value=fit.fun)
    assert gradient_check < 1e-3 and np.max(abs(fit.jac)) < 1e-3, f"gradient {np.max(abs(fit.jac)):.6g}; derivative error {gradient_check:.6g}"
    rng = np.random.default_rng(20261012 + int(context.fold))
    parameters = rng.multivariate_normal(fit.x, covariance, args.draws)
    count_draws = np.zeros((len(testing), args.draws))
    nodes, log_weights = gamma_quadrature(shape, 121)
    predicted, baseline_predicted, active_probability = [], [], []
    states = {date: rng.gamma(shape, 1 / shape, args.draws) for date in testing.date.unique()}
    for i, observation in enumerate(testing.itertuples()):
        rows = mapping[observation.observation_id]
        baseline_hazard = np.exp(np.clip(original_gate[rows], -30, 30))
        baseline_mean = np.exp(np.clip(original_count[rows], -30, 30))
        baseline_predicted.append(
            gamma_hour_moments(
                shape, shape, baseline_hazard, baseline_mean, np.full(len(rows), size), q[rows]
            )[0].sum()
        )
        hazard = np.exp(np.clip(gate_base[rows] + Z[rows] @ fit.x[:n], -30, 30))
        mean = np.exp(np.clip(count_base[rows] + Z[rows] @ fit.x[n:], -30, 30))
        predicted.append(
            gamma_hour_moments(shape, shape, hazard, mean, np.full(len(rows), size), q[rows])[
                0
            ].sum()
        )
        active_probability.append(gamma_interval_active(shape, shape, hazard, mean, size, q[rows]))
        h = np.exp(np.clip(gate_base[rows, None] + Z[rows] @ parameters[:, :n].T, -30, 30))
        mu = (
            np.exp(np.clip(count_base[rows, None] + Z[rows] @ parameters[:, n:].T, -30, 30))
            * states[observation.date]
        )
        positive = rng.uniform(size=h.shape) < -np.expm1(-h * states[observation.date])
        p0 = np.exp(-size * np.log1p(mu / size))
        uniforms = np.minimum(
            p0 + (-np.expm1(-size * np.log1p(mu / size))) * rng.uniform(size=mu.shape),
            np.nextafter(1.0, 0.0),
        )
        full_counts = np.zeros_like(mu, dtype=np.int64)
        full_counts[positive] = np.maximum(
            1, nbinom.ppf(uniforms[positive], size, size / (size + mu[positive]))
        ).astype(np.int64)
        count_draws[i] = rng.binomial(full_counts, q[rows, None]).sum(axis=0)
    result = testing.copy()
    result["predicted"], result["active_probability"] = predicted, active_probability
    result["fold"] = context.fold
    result["baseline_predicted"] = baseline_predicted
    for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
        if args.draws:
            result[label] = np.quantile(count_draws, probability, axis=1)
    result.to_csv(args.out / f"{key}_predictions.csv", index=False)
    dates_out, groups = np.unique(testing.date, return_inverse=True)
    daily_draws = np.zeros((len(dates_out), args.draws))
    np.add.at(daily_draws, groups, count_draws)
    np.savez_compressed(
        args.out / f"{key}_draws.npz",
        counts=count_draws,
        daily_counts=daily_draws,
        dates=dates_out.astype(str),
    )
    np.savez(
        args.out / f"{key}_fit.npz",
        parameters=fit.x,
        covariance=covariance,
        information=information,
        daily_shape=shape,
        positive_size=size,
        time_refitted=args.refit_time,
        extended_time=args.extended_time,
        rate_design_columns=n,
        uncertainty_available=bool(args.draws),
    )
    diagnostics.append(
        dict(
            english_name=context.english_name,
            fold=context.fold,
            converged=fit.success,
            time_refitted=args.refit_time,
            extended_time=args.extended_time,
            rate_coefficients=2 * n,
            predictive_draws=args.draws,
            gradient=np.max(abs(fit.jac)),
            gradient_check=gradient_check,
            integration_loss_delta=abs(refined_value - fit.fun) / len(dates),
            integration_gradient_delta=np.max(abs(refined_gradient - fit.jac)),
            training_hours=int(training.resolution.eq("hour").sum()),
            training_surveys=int(training.resolution.eq("survey").sum()),
            heldout_surveys=int(testing.resolution.eq("survey").sum()),
        )
    )
    results.append(result)
    pd.DataFrame([diagnostics[-1]]).to_csv(args.out / f"{key}_diagnostics.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(args.out / "fit_diagnostics.csv", index=False)
pd.concat(results, ignore_index=True).to_csv(args.out / "held_out_intervals.csv", index=False)
print(
    "Time refit: "
    + str(args.refit_time)
    + "; other GAM effects, daily shape, dispersion and smoothing remain conditional."
)
