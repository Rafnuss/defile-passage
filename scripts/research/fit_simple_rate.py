"""Fit a small mixed-interval mean-rate GAM with Poisson or fixed Tweedie variance.

Only means are modelled; predictive intervals, dispersion and retained-hour conditioning remain
outstanding. A working variance criterion does not define a coherent predictive count law.
"""

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

EPISODE_STRENGTHS = [10, 100, 1000]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--smoothing", type=float, default=10)
parser.add_argument("--select-smoothing", action="store_true")
parser.add_argument("--variance-power", type=float, choices=[1, 1.5], default=1)
parser.add_argument(
    "--variant",
    choices=[
        "baseline",
        "rain_weather",
        "rain_daylight",
        "cyclic_clock",
        "year_weather",
        "year_clear",
        "year_season_weather",
        "year_episode_weather",
    ],
    default="baseline",
)
parser.add_argument("--keys", nargs="+")
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(args.input / "manifest.csv")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
diagnostics, predictions = [], []


for context in manifest.itertuples():
    started = perf_counter()
    key = context.key
    observations = pd.read_csv(args.input / f"{key}_observations.csv")
    components = pd.read_csv(args.input / f"{key}_components.csv")
    suffix = "" if args.variant == "baseline" else f"_{args.variant}"
    X = np.loadtxt(args.input / f"{key}{suffix}_X.csv", delimiter=",")
    penalty = np.loadtxt(args.input / f"{key}{suffix}_penalty.csv", delimiter=",")
    # Keep a finite night coefficient when training night counts are all zero.
    night_penalty = np.zeros_like(penalty)
    if args.variant in ["rain_daylight", "cyclic_clock"]:
        night_penalty[-1, -1] = 1
    if args.variant in [
        "year_weather",
        "year_clear",
        "year_season_weather",
        "year_episode_weather",
    ]:
        linear = (
            [1, 15, 16, 17, 18, 19, 20, 21] if args.variant != "year_clear" else [14, 15, 16, 17]
        )
        night_penalty[linear, linear] = 1
        if args.variant == "year_weather":
            night_penalty[19:, 19:] = np.eye(X.shape[1] - 19)
        if args.variant == "year_clear":
            night_penalty[15:, 15:] = np.eye(X.shape[1] - 15)
        if args.variant == "year_season_weather":
            night_penalty[22:, 22:] = np.eye(6)
    indices = observations.set_index("observation_id").index.get_indexer(components.observation_id)
    A = csr_matrix(
        (components.fraction, (indices, np.arange(len(components)))),
        shape=(len(observations), len(components)),
    )
    hidden = (
        observations.hidden.to_numpy()
        if "hidden" in observations
        else pd.to_datetime(observations.date).dt.year.eq(context.heldout_year).to_numpy()
    )
    y = observations["count"].to_numpy()[~hidden]
    training = A[~hidden]
    episode_strength = 0
    episode_penalty = np.zeros_like(penalty)
    if args.variant == "year_episode_weather":
        episode_penalty = np.loadtxt(
            args.input / f"{key}{suffix}_episode_penalty.csv", delimiter=","
        )
        episode_strength = 100
    selection_X = X[:, :22] if args.variant == "year_episode_weather" else X
    selection_penalty = penalty[:22, :22] if args.variant == "year_episode_weather" else penalty
    selection_ridge = (
        night_penalty[:22, :22] if args.variant == "year_episode_weather" else night_penalty
    )
    smoothing = args.smoothing
    if args.select_smoothing:
        dates = pd.to_datetime(observations.loc[~hidden, "date"])
        weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
        scores = []
        for strength in [1, 10, 100] if args.variance_power == 1 else [0.1, 1, 10]:
            held = np.zeros(len(y))
            for fold in range(3):
                mask = weeks % 3 == fold
                fit, _ = fit_rate(
                    selection_X,
                    training[~mask],
                    y[~mask],
                    strength * selection_penalty + selection_ridge,
                    args.variance_power,
                )
                assert np.abs(fit.jac).max() < 0.001, (
                    key,
                    strength,
                    fold,
                    fit.message,
                    np.abs(fit.jac).max(),
                )
                held[mask] = training[mask] @ np.exp(selection_X @ fit.x)
            daily = pd.DataFrame({"date": dates.to_numpy(), "count": y, "predicted": held})
            daily = daily.groupby("date")[["count", "predicted"]].sum()
            scores.append(
                dict(smoothing=strength, daily_mae=(daily["count"] - daily.predicted).abs().mean())
            )
        pd.DataFrame(scores).to_csv(args.out / f"{key}_smoothing_scores.csv", index=False)
        smoothing = min(scores, key=lambda row: row["daily_mae"])["smoothing"]
    if args.variant == "year_episode_weather" and args.select_smoothing:
        # Select local variation separately; all scoring stays inside the outer training set.
        episode_scores = []
        for strength in EPISODE_STRENGTHS:
            held = np.zeros(len(y))
            for fold in range(3):
                mask = weeks % 3 == fold
                fit, _ = fit_rate(
                    X,
                    training[~mask],
                    y[~mask],
                    smoothing * penalty + night_penalty + strength * episode_penalty,
                    args.variance_power,
                )
                assert np.abs(fit.jac).max() < 0.001, (key, strength, fold, fit.message)
                held[mask] = training[mask] @ np.exp(X @ fit.x)
            daily = (
                pd.DataFrame({"date": dates.to_numpy(), "count": y, "predicted": held})
                .groupby("date")[["count", "predicted"]]
                .sum()
            )
            episode_scores.append(
                dict(
                    episode_strength=strength,
                    daily_mae=(daily["count"] - daily.predicted).abs().mean(),
                )
            )
        pd.DataFrame(episode_scores).to_csv(args.out / f"{key}_episode_scores.csv", index=False)
        episode_strength = min(episode_scores, key=lambda row: row["daily_mae"])[
            "episode_strength"
        ]
    result, objective = fit_rate(
        X,
        training,
        y,
        smoothing * penalty + night_penalty + episode_strength * episode_penalty,
        args.variance_power,
    )
    gradient = np.abs(result.jac).max()
    derivative = check_rate_gradient(objective, result.x)
    assert gradient < 0.001 and derivative < 0.001, (key, gradient, derivative)
    predicted = A @ np.exp(X @ result.x)
    output = observations[hidden].copy()
    output["predicted"] = predicted[hidden]
    output["english_name"] = context.english_name
    output["fold"] = context.fold
    predictions.append(output)
    np.savez(
        args.out / f"{key}_fit.npz",
        coefficients=result.x,
        smoothing=smoothing,
        variance_power=args.variance_power,
        episode_strength=episode_strength,
    )
    if args.variant.startswith("year_"):
        coefficients = pd.read_csv(args.input / f"{key}{suffix}_terms.csv")
        coefficients["coefficient"] = result.x
        coefficients.to_csv(args.out / f"{key}_coefficients.csv", index=False)
    output.to_csv(args.out / f"{key}_predictions.csv", index=False)
    diagnostics.append(
        dict(
            key=key,
            variant=args.variant,
            variance_power=args.variance_power,
            coefficients=len(result.x),
            episode_strength=episode_strength,
            seconds=perf_counter() - started,
            iterations=result.nit,
            gradient=gradient,
            derivative_error=derivative,
            rain_coefficient=result.x[1] if args.variant != "year_clear" else np.nan,
            smoothing=smoothing,
            heldout_mae=np.abs(output["count"] - output.predicted).mean(),
            uncertainty_available=False,
        )
    )
    print(diagnostics[-1], flush=True)
pd.DataFrame(diagnostics).to_csv(args.out / "diagnostics.csv", index=False)
pd.concat(predictions, ignore_index=True).to_csv(args.out / "predictions.csv", index=False)
