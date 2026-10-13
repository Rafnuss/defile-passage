"""Reconcile finished fit outputs using a common stable forward-integration rule."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from adaptive_daily_integration import adaptive_hurdle_rule, hurdle_log_rows
from gamma_count_moments import gamma_hour_moments
from scipy.special import logsumexp

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--prefix", required=True)
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
args = parser.parse_args()
for panel in args.panels:
    for suffix in ["", "-year"]:
        folder = ROOT / f"logs/{args.prefix}-{panel}{suffix}"
        prepared = ROOT / f"logs/hourly-weather-{panel}{suffix}"
        manifest = pd.read_csv(prepared / "manifest.csv").query("fold>=5" if suffix else "fold<4")
        diagnostics = pd.read_csv(folder / "shared_activity_fit_diagnostics.csv")
        output = []
        for record in manifest.itertuples():
            key = record.key
            frame = pd.read_csv(folder / f"{key}_hours.csv")
            train = pd.read_csv(prepared / f"{key}_train.csv")
            test = pd.read_csv(prepared / f"{key}_test.csv")
            X = np.loadtxt(prepared / f"{key}_Xtrain.csv", delimiter=",")
            Xt = np.loadtxt(prepared / f"{key}_Xtest.csv", delimiter=",")
            fit = np.load(folder / f"{key}_shared_activity_fit.npz")
            a, kappa = float(fit["daily_shape"]), float(fit["positive_shape"])
            h = train.exposure_hours.to_numpy() * np.exp(
                np.clip(X @ fit["occurrence_coefficients"], -30, 30)
            )
            mu = train.exposure_hours.to_numpy() * np.exp(
                np.clip(X @ fit["positive_count_coefficients"], -30, 30)
            )
            ht = test.exposure_hours.to_numpy() * np.exp(
                np.clip(Xt @ fit["occurrence_coefficients"], -30, 30)
            )
            mt = test.exposure_hours.to_numpy() * np.exp(
                np.clip(Xt @ fit["positive_count_coefficients"], -30, 30)
            )
            size = kappa * train.exposure_hours.to_numpy()
            st = kappa * test.exposure_hours.to_numpy()
            maximum_difference, maximum_relative = 0.0, 0.0
            for date in test.date.unique():
                retained, hidden = np.flatnonzero(train.date.eq(date)), np.flatnonzero(
                    test.date.eq(date)
                )
                predictions, probabilities = [], []
                if not len(retained) or not train["count"].to_numpy()[retained].any():
                    rate = a + h[retained].sum()
                    for order in [121, 243]:
                        mean, active = gamma_hour_moments(
                            a, rate, ht[hidden], mt[hidden], st[hidden], order=order
                        )
                        predictions.append(mean)
                        probabilities.append(active)
                else:
                    y = train["count"].to_numpy()[retained]
                    for order in [31, 63]:
                        nodes, weights = adaptive_hurdle_rule(
                            a, y, h[retained], mu[retained], size[retained], order
                        )
                        joint = weights + hurdle_log_rows(
                            nodes, y, h[retained], mu[retained], size[retained]
                        ).sum(axis=0)
                        posterior = np.exp(joint - logsumexp(joint))
                        gate = -np.expm1(-ht[hidden, None] * nodes)
                        positive_mean = (
                            mt[hidden, None]
                            * nodes
                            / (
                                -np.expm1(
                                    -st[hidden, None]
                                    * np.log1p(mt[hidden, None] * nodes / st[hidden, None])
                                )
                            )
                        )
                        predictions.append((gate * positive_mean) @ posterior)
                        probabilities.append(gate @ posterior)
                delta = abs(predictions[1] - predictions[0])
                maximum_difference = max(maximum_difference, float(delta.max()))
                maximum_relative = max(
                    maximum_relative, float((delta / (0.01 + 0.001 * predictions[1])).max())
                )
                frame.loc[hidden, "predicted"] = predictions[1]
                frame.loc[hidden, "active_probability"] = probabilities[1]
            frame.to_csv(folder / f"{key}_hours.csv", index=False)
            index = diagnostics.english_name.eq(record.english_name) & diagnostics.fold.eq(
                record.fold
            )
            diagnostics.loc[index, "forward_mean_max_delta"] = maximum_difference
            diagnostics.loc[index, "forward_mean_tolerance_ratio"] = maximum_relative
            diagnostics.loc[index].to_csv(folder / f"{key}_diagnostics.csv", index=False)
            output.append(frame)
        hours = pd.concat(output, ignore_index=True)
        hours.to_csv(folder / "shared_activity_held_out_hours.csv", index=False)
        days = pd.read_csv(folder / "shared_activity_held_out_days.csv")
        totals = hours.groupby(["english_name", "date", "fold"], as_index=False).predicted.sum()
        days = days.drop(columns="predicted").merge(
            totals, on=["english_name", "date", "fold"], validate="one_to_one"
        )
        days.to_csv(folder / "shared_activity_held_out_days.csv", index=False)
        diagnostics.to_csv(folder / "shared_activity_fit_diagnostics.csv", index=False)
        print(
            f"{folder.name}: stable means reconciled; forward flags {(diagnostics.forward_mean_tolerance_ratio>1).sum()} / {len(diagnostics)}"
        )
