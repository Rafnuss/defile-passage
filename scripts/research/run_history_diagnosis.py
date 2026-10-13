"""Fit controlled training-data comparisons without changing the mean model."""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/history-diagnosis"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
manifest = pd.read_csv(OUT / "input/manifest.csv")
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
status = []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "run.log").open("w") as log:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/research/fit_simple_rate.py",
                "--input",
                str(OUT / "design"),
                "--out",
                str(folder),
                "--variant",
                "year_weather",
                "--keys",
                context.key,
                "--select-smoothing",
                "--variance-power",
                "1.5",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    status.append(dict(key=context.key, passed=result.returncode == 0))
    if result.returncode:
        continue
    obs = pd.read_csv(OUT / f"design/{context.key}_observations.csv")
    parts = pd.read_csv(OUT / f"design/{context.key}_components.csv")
    parts["rain_hours"] = parts.rain_mm * parts.fraction
    rain = (
        parts[parts.hidden]
        .groupby("date")
        .agg(rain_hours=("rain_hours", "sum"), hours=("fraction", "sum"))
    )
    prediction = pd.read_csv(folder / "predictions.csv")
    daily = (
        prediction.groupby("date")
        .agg(count=("count", "sum"), predicted=("predicted", "sum"))
        .join(rain)
    )
    daily["weather"] = np.where(daily.rain_hours / daily.hours >= 0.1, "wet", "dry")
    daily["year"] = pd.to_datetime(daily.index).year
    daily["english_name"], daily["fold"], daily["arm"] = (
        context.english_name,
        context.fold,
        context.arm,
    )
    daily.reset_index().to_csv(folder / "assessment.csv", index=False)
    if context.arm == "recent":
        saved = np.load(
            ROOT
            / f"logs/simple-gaps-tweedie-priority/year_weather/{context.original_key}/{context.original_key}_fit.npz"
        )
        current = np.load(folder / f"{context.key}_fit.npz")
        difference = np.abs(current["coefficients"] - saved["coefficients"]).max()
        assert np.allclose(current["coefficients"], saved["coefficients"], atol=1e-7, rtol=1e-7)
        assert current["smoothing"] == saved["smoothing"]
        (folder / "regression.txt").write_text(f"Maximum coefficient difference: {difference}\n")
    print(context.key, "completed", flush=True)
pd.DataFrame(status).to_csv(OUT / f"status-{args.shard[0]}.csv", index=False)
