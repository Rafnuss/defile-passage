"""Audit saved activity coefficients, convergence and likelihood derivatives."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs/weather-activity-numerical-review"
OUTPUT.mkdir(parents=True, exist_ok=True)
diagnostics, quadrature = [], []
for group in ["priority", "passerines"]:
    manifest = pd.read_csv(ROOT / f"logs/hourly-weather-{group}/manifest.csv").query("fold < 4")
    for prefix in ["weather-activity", "weather-activity-positive10", "shared-activity"]:
        shared = prefix == "shared-activity"
        folder = ROOT / f"logs/{prefix}-{group}"
        filename = (
            "shared_activity_fit_diagnostics.csv" if shared else "activity_fit_diagnostics.csv"
        )
        fits = pd.read_csv(folder / filename)
        assert len(fits) == len(manifest)
        if shared:
            assert fits.converged.all() and (fits.gradient_check < 1e-3).all()
            assert (fits.start_gradient_check < 1e-3).all()
        else:
            assert fits.activity_converged.all() and fits.positive_converged.all()
            assert (fits.activity_gradient_check < 1e-3).all() and (
                fits.positive_gradient_check < 1e-3
            ).all()
        diagnostics.append(fits.assign(panel=group, experiment=prefix))
        for record in manifest.itertuples():
            suffix = "shared_activity_fit.npz" if shared else "activity_fit.npz"
            saved = np.load(folder / f"{record.key}_{suffix}")
            for component in ["occurrence_coefficients", "positive_count_coefficients"]:
                assert (
                    saved[component].shape == (record.coefficients,)
                    and np.isfinite(saved[component]).all()
                )
            if shared:
                weights = np.exp(saved["quadrature_log_weights"])
                nodes = saved["quadrature_nodes"]
                shape = float(saved["daily_shape"])
                quadrature.append(
                    dict(
                        key=record.key,
                        panel=group,
                        shape=shape,
                        mass_error=abs(weights.sum() - 1),
                        mean_error=abs(weights @ nodes - 1),
                        variance_relative_error=abs(weights @ (nodes - 1) ** 2 * shape - 1),
                    )
                )
fits = pd.concat(diagnostics, ignore_index=True)
fits.to_csv(OUTPUT / "fit_diagnostics.csv", index=False)
moments = pd.DataFrame(quadrature)
assert (moments[["mass_error", "mean_error", "variance_relative_error"]] < 1e-8).all().all()
moments.to_csv(OUTPUT / "quadrature_moments.csv", index=False)
print(
    fits.groupby(["experiment", "panel"])[
        [
            "activity_gradient",
            "positive_gradient",
            "activity_gradient_check",
            "positive_gradient_check",
            "gradient",
            "gradient_check",
            "start_gradient_check",
        ]
    ]
    .max()
    .to_string()
)
print(
    "\nAll saved coefficient dimensions, optimizer statuses, directional derivatives and quadrature moments verified"
)
print("These moment checks do not establish quadrature convergence for the full daily likelihood.")
