"""Locate weakly identified rate predictions behind wide Gaussian predictive draws."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
parser.add_argument("--prefix", default="shared-uncertainty")
parser.add_argument("--out", type=Path, default=ROOT / "logs/shared-coefficient-support")
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
rows = []
for panel in args.panels:
    for suffix in ["", "-year"]:
        inputs = ROOT / f"logs/hourly-weather-{panel}{suffix}"
        fits = ROOT / f"logs/{args.prefix}-{panel}{suffix}"
        manifest = pd.read_csv(inputs / "manifest.csv").query(
            "fold >= 5" if suffix else "fold < 4"
        )
        for context in manifest.itertuples():
            fit = np.load(fits / f"{context.key}_shared_activity_fit.npz")
            covariance = fit["coefficient_covariance"]
            n = covariance.shape[0] // 2
            for partition in ["train", "test"]:
                design = np.loadtxt(inputs / f"{context.key}_X{partition}.csv", delimiter=",")
                frame = pd.read_csv(inputs / f"{context.key}_{partition}.csv")
                for component, block in [
                    ("occurrence", covariance[:n, :n]),
                    ("positive", covariance[n:, n:]),
                ]:
                    variance = np.einsum("ij,jk,ik->i", design, block, design)
                    uncertainty = np.sqrt(np.maximum(variance, 0))
                    rows.append(
                        dict(
                            english_name=context.english_name,
                            fold=context.fold,
                            validation="year" if suffix else "blocked",
                            partition=partition,
                            component=component,
                            rows=len(frame),
                            positive_hours=int(frame["count"].gt(0).sum()),
                            median_log_rate_sd=np.median(uncertainty),
                            q95_log_rate_sd=np.quantile(uncertainty, 0.95),
                            max_log_rate_sd=uncertainty.max(),
                            max_sd_date=frame.iloc[uncertainty.argmax()].date,
                        )
                    )
scores = pd.DataFrame(rows)
scores.to_csv(args.out / "log_rate_uncertainty.csv", index=False)
print(
    scores.query("partition == 'test' and component == 'positive'")
    .nlargest(10, "max_log_rate_sd")
    .to_string(index=False)
)
print(
    "Gaussian log-rate variance implies a mean multiplier exp(variance/2); large values need scientific assessment before use."
)
