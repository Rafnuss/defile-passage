"""Audit saved daily-passage checkpoints and bias; never refit or correct fills."""

from pathlib import Path

import numpy as np
import pandas as pd
from daily_passage_diagnostics import conditional_daily_variance, observed_information
from daily_passage_model import (
    ar1_penalty,
    center_daily,
    daily_objective,
    scoring_information,
    scoring_step,
)
from scipy.sparse import csr_matrix

from defile_explore.export import WINDOW

OUT = Path("logs/daily-passage-diagnosis")
SOURCE = Path("logs/history-episode")
FITS = Path("logs/daily-passage")
OUT.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(FITS / "design/manifest.csv")
checkpoints = pd.read_csv(FITS / "all_final_checks.csv")
checkpoints = checkpoints[checkpoints.method.eq("weather_daily")].merge(manifest, on="key")
failures = pd.read_csv(FITS / "numerical_failures.csv")
trajectories = []
for row in failures.itertuples():
    folder = FITS / "fits" / row.key
    if row.stage == "inner":
        history = pd.read_csv(folder / "cv_history.csv")
        history = history[history.sd.eq(row.sd) & history.fold.eq(row.fold)]
    else:
        history = pd.read_csv(folder / "weather_daily_history.csv")
    tail = history.tail(21)
    trajectories.append(
        dict(
            key=row.key,
            stage=row.stage,
            sd=row.sd,
            fold=row.fold,
            final_gradient=tail.gradient.iloc[-1],
            per_update_gradient_ratio=(tail.gradient.iloc[-1] / tail.gradient.iloc[0])
            ** (1 / (len(tail) - 1)),
            last_20_loss_decrease=tail.loss.iloc[0] - tail.loss.iloc[-1],
            last_20_full_steps=tail.step.iloc[1:].eq(1).sum(),
            endpoint_coefficients_available=row.stage == "final",
        )
    )
pd.DataFrame(trajectories).to_csv(OUT / "failed_trajectories.csv", index=False)

numerical, support, frames = [], [], []
for context in checkpoints.itertuples():
    key = context.key
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
    parts = pd.read_csv(SOURCE / f"design/{key}_components.csv", low_memory=False)
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    training, y = A[~hidden], obs.loc[~hidden, "count"].to_numpy()
    X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
    ridge = np.diag(
        (
            terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
            | terms.str.startswith("factor(year)")
        ).astype(float)
    )
    smoothing = float(np.load(SOURCE / f"fits/{key}/weather_mean_fit.npz")["smoothing"])
    penalty = smoothing * P + ridge
    calendar = pd.DatetimeIndex(
        [
            date
            for year in sorted(parts.year.unique())
            for date in pd.date_range(
                pd.Timestamp(year, *WINDOW[0]), pd.Timestamp(year, *WINDOW[1])
            )
        ]
    )
    years = pd.factorize(calendar.year)[0]
    day = calendar.get_indexer(pd.to_datetime(parts.date))
    assert day.min() >= 0
    n, p = len(calendar), X.shape[1]
    C = csr_matrix((np.ones(n), (years, np.arange(n))))
    Z = csr_matrix((np.ones(len(day)), (np.arange(len(day)), day)), shape=(len(day), n))
    saved = np.load(FITS / f"fits/{key}/weather_daily_fit.npz")
    Q = ar1_penalty(years, float(saved["sd"]))
    parameters = np.r_[saved["coefficients"], saved["daily"]]
    objective = daily_objective(X, training, y, penalty, Q, day, years)
    _, gradient = objective(parameters)
    assert np.isclose(abs(gradient).max(), context.gradient, atol=1e-12, rtol=1e-8)
    rate = np.exp(X @ saved["coefficients"] + saved["daily"][day])
    bb, cross, uu, _, _, _ = scoring_information(X, training, penalty, Q, Z, rate)
    direction, _ = scoring_step(bb, cross, uu, C, gradient[:, None])
    direction = direction[:, 0]
    actual_bb, actual_cross, actual_uu = observed_information(X, training, y, penalty, Q, Z, rate)
    product = np.r_[
        actual_bb @ direction[:p] + actual_cross @ direction[p:],
        center_daily(actual_cross.T @ direction[:p] + actual_uu @ direction[p:], years),
    ]
    # Verify the observed directional curvature at the frozen parameters.
    unit = direction / np.linalg.norm(direction)
    finite = (objective(parameters + 1e-4 * unit)[1] - objective(parameters - 1e-4 * unit)[1]) / (
        2e-4
    )
    analytic = product / np.linalg.norm(direction)
    hvp_error = abs(finite - analytic).max() / max(1, abs(analytic).max())
    assert hvp_error < 1e-5, (key, hvp_error)
    dominant = np.argmax(abs(gradient))
    numerical.append(
        dict(
            key=key,
            task=context.task,
            numerical_pass=context.gradient < 0.001,
            gradient=abs(gradient).max(),
            shared_gradient=abs(gradient[:p]).max(),
            daily_gradient=abs(gradient[p:]).max(),
            dominant_component=terms.iloc[dominant]
            if dominant < p
            else str(calendar[dominant - p].date()),
            observed_hvp_error=hvp_error,
            observed_to_scoring_directional_curvature=(direction @ product)
            / (gradient @ direction),
            linearized_scoring_gradient_ratio=abs(gradient - product).max() / abs(gradient).max(),
            unapplied_max_log_rate_step=abs(X @ direction[:p] + direction[p:][day]).max(),
        )
    )
    # Year blocks are valid only if observations have not coupled different years.
    rows, cols = actual_uu.nonzero()
    assert (years[rows] == years[cols]).all()
    variance = conditional_daily_variance(actual_uu, years)
    assert (variance > 0).all()
    if not (FITS / f"fits/{key}/assessment.csv").exists():
        continue
    base = np.load(FITS / f"fits/{key}/weather_mean_fit.npz")
    base_rate = np.exp(X @ base["coefficients"])
    shared_rate = np.exp(X @ saved["coefficients"])
    for mask, label in [(~hidden, "retained"), (hidden, "hidden")]:
        weights = np.asarray(A[mask].sum(axis=0)).ravel()
        mean = A[mask] @ rate
        count = obs.loc[mask, "count"].to_numpy()
        support.append(
            dict(
                key=key,
                task=context.task,
                english_name=context.english_name,
                support=label,
                sd=float(saved["sd"]),
                observed_count=count.sum(),
                base_total=weights @ base_rate,
                shared_only_total=weights @ shared_rate,
                candidate_total=weights @ rate,
                shared_to_base_ratio=(weights @ shared_rate) / (weights @ base_rate),
                daily_multiplier=(weights @ rate) / (weights @ shared_rate),
                conditional_gaussian_factor=(weights @ (rate * np.exp(variance[day] / 2)))
                / (weights @ rate),
                rate_weighted_conditional_variance=(weights @ (rate * variance[day]))
                / (weights @ rate),
                intercept_score=((mean - count) / np.sqrt(mean)).sum()
                if label == "retained"
                else np.nan,
            )
        )
    grouped = (
        obs[hidden][["date", "count"]]
        .assign(
            base=A[hidden] @ base_rate,
            shared_only=A[hidden] @ shared_rate,
            daily=A[hidden] @ rate,
        )
        .groupby("date")
        .sum()
        .reset_index()
    )
    target = pd.read_csv(FITS / f"fits/{key}/assessment.csv")
    grouped = grouped.merge(
        target[["date", "weather_mean", "weather_daily", "weather", "year"]],
        on="date",
        validate="one_to_one",
    )
    assert np.allclose(grouped.base, grouped.weather_mean, atol=1e-8, rtol=1e-10)
    assert np.allclose(grouped.daily, grouped.weather_daily, atol=1e-8, rtol=1e-10)
    grouped["key"], grouped["task"], grouped["english_name"] = (
        key,
        context.task,
        context.english_name,
    )
    frames.append(grouped)
    print(key, "saved checkpoint audited", flush=True)
pd.DataFrame(numerical).to_csv(OUT / "checkpoint_curvature.csv", index=False)
support = pd.DataFrame(support)
support["baseline_bias"] = (support.base_total - support.observed_count) / support.observed_count
support["shared_change"] = (
    support.shared_only_total - support.base_total
) / support.observed_count
support["daily_change"] = (
    support.candidate_total - support.shared_only_total
) / support.observed_count
support["candidate_bias"] = (
    support.candidate_total - support.observed_count
) / support.observed_count
assert np.allclose(
    support.baseline_bias + support.shared_change + support.daily_change, support.candidate_bias
)
support.to_csv(OUT / "support_decomposition.csv", index=False)
support["gaussian_factor_mass"] = support.candidate_total * support.conditional_gaussian_factor
summary = support.groupby(["task", "support", "english_name"])[
    [
        "observed_count",
        "base_total",
        "shared_only_total",
        "candidate_total",
        "gaussian_factor_mass",
    ]
].sum()
summary["baseline_bias"] = (summary.base_total - summary.observed_count) / summary.observed_count
summary["shared_change"] = (
    summary.shared_only_total - summary.base_total
) / summary.observed_count
summary["daily_change"] = (
    summary.candidate_total - summary.shared_only_total
) / summary.observed_count
summary["candidate_bias"] = (
    summary.candidate_total - summary.observed_count
) / summary.observed_count
summary["conditional_gaussian_factor"] = summary.gaussian_factor_mass / summary.candidate_total
summary.groupby(["task", "support"])[
    [
        "baseline_bias",
        "shared_change",
        "daily_change",
        "candidate_bias",
        "conditional_gaussian_factor",
    ]
].mean().to_csv(OUT / "support_summary.csv")
wide = pd.concat(frames, ignore_index=True)
wide["peak_threshold"] = wide.groupby(["task", "english_name"])["count"].transform(
    lambda x: x.quantile(0.9)
)
wide["count_group"] = np.where(
    wide["count"].eq(0),
    "zero",
    np.where(wide["count"] > wide.peak_threshold, "peak", "other_positive"),
)
original = pd.read_csv(FITS / "predictions.csv")
original = original[original.method.eq("original_episode")][
    ["date", "task", "english_name", "fold", "predicted"]
]
wide = wide.merge(manifest[["key", "fold"]], on="key", validate="many_to_one")
wide = wide.merge(original, on=["date", "task", "english_name", "fold"], validate="one_to_one")
wide = wide.rename(columns={"predicted": "original_episode"})
long = wide.melt(
    id_vars=["key", "date", "task", "english_name", "count", "count_group", "weather", "year"],
    value_vars=["base", "shared_only", "daily", "original_episode"],
    var_name="method",
    value_name="predicted",
)
long["error"] = long.predicted - long["count"]
long["absolute_error"] = abs(long.error)
long.to_csv(OUT / "bias_components.csv", index=False)
denominator = wide.groupby(["task", "english_name"])["count"].sum().rename("all_hidden_count")
strata = long.groupby(["task", "english_name", "count_group", "method"]).agg(
    error=("error", "sum"),
    mae=("absolute_error", "mean"),
    days=("date", "size"),
    count=("count", "sum"),
)
complete_groups = pd.MultiIndex.from_tuples(
    [
        (task, name, group, method)
        for task, name in denominator.index
        for group in ["zero", "other_positive", "peak"]
        for method in long.method.unique()
    ],
    names=["task", "english_name", "count_group", "method"],
)
strata = strata.reindex(complete_groups)
strata[["error", "days", "count"]] = strata[["error", "days", "count"]].fillna(0)
strata = strata.join(denominator)
strata["bias_contribution"] = strata.error / strata.all_hidden_count
strata.to_csv(OUT / "count_group_species.csv")
strata.groupby(["task", "count_group", "method"])[["mae", "bias_contribution"]].mean().to_csv(
    OUT / "count_group_summary.csv"
)
long.groupby(["task", "year", "english_name", "method"]).agg(
    count=("count", "sum"), predicted=("predicted", "sum"), error=("error", "sum")
).to_csv(OUT / "year_bias_components.csv")
print("Saved-fit audit completed without fitting, applying steps or correcting predictions.")
