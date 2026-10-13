"""Review the finished amplitude screen, preserving every numerical failure."""

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, default=Path("logs/daily-passage"))
args = parser.parse_args()
OUT = args.out
manifest = pd.read_csv(OUT / "design/manifest.csv")
failures = pd.concat(
    [pd.read_csv(p) for p in sorted(OUT.glob("failures-*.csv"))], ignore_index=True
)
failures.to_csv(OUT / "failures.csv", index=False)
inner, final = [], []
for key in manifest.key:
    folder = OUT / "fits" / key
    if (folder / "cv_checks.csv").exists():
        inner.append(pd.read_csv(folder / "cv_checks.csv").assign(key=key))
    if (folder / "diagnostics.csv").exists():
        final.append(pd.read_csv(folder / "diagnostics.csv"))
checks = pd.concat(inner, ignore_index=True)
checks["numerical_pass"] = (
    checks.gradient.lt(0.001) & checks.derivative_error.lt(0.001) & checks.center_error.lt(1e-9)
)
checks.to_csv(OUT / "cv_checks.csv", index=False)
print("Inner numerical checks:", len(checks), "of", len(manifest) * 12)
print(
    checks.groupby("sd")
    .agg(
        fits=("key", "size"),
        numerical_pass=("numerical_pass", "sum"),
        max_gradient=("gradient", "max"),
        max_derivative=("derivative_error", "max"),
    )
    .to_string()
)
print("Explicit failed contexts:", len(failures))
print(failures.to_string(index=False))
if not final:
    raise SystemExit("No final fits; no efficacy comparison possible.")
final = pd.concat(final, ignore_index=True)
final.to_csv(OUT / "all_final_checks.csv", index=False)
pd.concat(
    [
        checks[~checks.numerical_pass].assign(stage="inner"),
        final[final.gradient.ge(0.001) | final.derivative_error.ge(0.001)].assign(stage="final"),
    ],
    ignore_index=True,
).to_csv(OUT / "numerical_failures.csv", index=False)
completed = manifest.key.map(lambda key: (OUT / "fits" / key / "assessment.csv").exists())
if not completed.any():
    raise SystemExit("No numerically accepted outer predictions; no efficacy comparison possible.")
subprocess.run(
    [
        sys.executable,
        "scripts/research/review_history_season.py",
        "--root",
        str(OUT),
        "--candidate",
        "weather_daily",
        "--allow-incomplete",
    ],
    check=True,
)
diagnostics = pd.read_csv(OUT / "diagnostics.csv")
selected = diagnostics[diagnostics.method.eq("weather_daily")].merge(manifest, on="key")
selected.groupby(["task", "sd"]).size().rename("contexts").to_csv(OUT / "selected_amplitude.csv")
print("Selected SD, completed contexts:", selected.groupby(["task", "sd"]).size().to_string())
print(
    "Final/selection seconds:",
    selected[["final_seconds", "selection_seconds", "seconds"]].agg(["median", "max"]).to_string(),
)
print(
    "Working effective DF:",
    selected.groupby("sd").effective_df.agg(["min", "median", "max"]).to_string(),
)
predictions = pd.read_csv(OUT / "predictions.csv")
bias = (
    pd.concat([predictions, predictions.assign(weather="all")])
    .groupby(["task", "weather", "english_name", "method"])
    .agg(error=("error", "sum"), count=("count", "sum"))
)
bias["relative_bias"] = bias.error / bias["count"]
bias.to_csv(OUT / "species_total_bias.csv")
bias.groupby(["task", "weather", "method"]).relative_bias.mean().to_csv(
    OUT / "group_total_bias.csv"
)
season = pd.read_csv(OUT / "season_errors.csv")
season["relative_bias"] = season.bias / season.observed_truth
season.groupby(["english_name", "method"]).relative_bias.mean().groupby("method").mean().to_csv(
    OUT / "season_bias.csv"
)
print(
    "Historical signed season bias:", pd.read_csv(OUT / "season_bias.csv").to_string(index=False)
)

# Resample historical years jointly across the matched species for season errors.
wide = season.pivot(
    index=["english_name", "year"], columns="method", values="absolute_relative_error"
)
years = sorted(wide.index.get_level_values("year").unique())
weights = np.random.default_rng(20261012).multinomial(
    len(years), np.full(len(years), 1 / len(years)), size=2000
)
paired = []
for reference in ["weather_mean", "original_episode"]:
    difference = (wide.weather_daily - wide[reference]).unstack("year").reindex(columns=years)
    present = difference.notna().to_numpy().astype(float)
    draws = ((weights @ difference.fillna(0).to_numpy().T) / (weights @ present.T)).mean(axis=1)
    paired.append(
        dict(
            reference=reference,
            difference=difference.mean(axis=1).mean(),
            low=np.quantile(draws, 0.025),
            high=np.quantile(draws, 0.975),
            species=len(difference),
            years=len(years),
        )
    )
pd.DataFrame(paired).to_csv(OUT / "paired_season_scores.csv", index=False)
print("Paired historical season error:", pd.DataFrame(paired).to_string(index=False))
