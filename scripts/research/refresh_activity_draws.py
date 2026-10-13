"""Refresh predictive draws from saved coefficients without refitting likelihoods."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from shared_activity_prediction import joint_count_draws

parser = argparse.ArgumentParser()
parser.add_argument("--prefix", required=True)
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
parser.add_argument("--draws", type=int, default=300)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
for panel in args.panels:
    folder = root / f"logs/{args.prefix}-{panel}"
    prepared = root / f"logs/hourly-weather-{panel}"
    manifest = pd.read_csv(prepared / "manifest.csv")
    manifest = manifest[manifest.fold.lt(4)]
    frames = []
    for record in manifest.itertuples():
        key = record.key
        fit = np.load(folder / f"{key}_shared_activity_fit.npz")
        training = pd.read_csv(prepared / f"{key}_train.csv")
        testing = pd.read_csv(prepared / f"{key}_test.csv")
        result = pd.read_csv(folder / f"{key}_hours.csv")
        counts, means, scores, activity = joint_count_draws(
            training,
            testing,
            np.loadtxt(prepared / f"{key}_Xtrain.csv", delimiter=","),
            np.loadtxt(prepared / f"{key}_Xtest.csv", delimiter=","),
            fit["occurrence_coefficients"],
            fit["positive_count_coefficients"],
            fit["coefficient_covariance"],
            float(fit["daily_shape"]),
            float(fit["positive_shape"]),
            fit["quadrature_nodes"],
            fit["quadrature_log_weights"],
            args.draws,
            np.random.default_rng(
                20261011 + int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
            ),
            adaptive=True,
        )
        result["predictive_mean"] = means.mean(axis=1)
        result["mean_mcse"] = means.std(axis=1) / np.sqrt(args.draws)
        result["log_score"], result["predictive_active_probability"] = scores, activity
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            result[label] = np.quantile(counts, probability, axis=1)
        dates, groups = np.unique(testing.date, return_inverse=True)
        daily = np.zeros((len(dates), args.draws))
        np.add.at(daily, groups, counts)
        np.savez_compressed(
            folder / f"{key}_predictive_draws.npz",
            hourly_counts=counts,
            daily_counts=daily,
            dates=dates.astype(str),
            date_group=groups,
        )
        result.to_csv(folder / f"{key}_hours.csv", index=False)
        frames.append(result)
    hours = pd.concat(frames, ignore_index=True)
    hours.to_csv(folder / "shared_activity_held_out_hours.csv", index=False)
    days = pd.read_csv(folder / "shared_activity_held_out_days.csv")
    for record in manifest.itertuples():
        draws = np.load(folder / f"{record.key}_predictive_draws.npz")
        index = days.english_name.eq(record.english_name) & days.fold.eq(record.fold)
        for probability, label in zip([0.025, 0.1, 0.9, 0.975], ["q025", "q10", "q90", "q975"]):
            quantiles = pd.Series(
                np.quantile(draws["daily_counts"], probability, axis=1), index=draws["dates"]
            )
            days.loc[index, label] = days.loc[index, "date"].map(quantiles)
    days.to_csv(folder / "shared_activity_held_out_days.csv", index=False)
    print(f"{panel}: refreshed {len(manifest)} saved contexts", flush=True)
