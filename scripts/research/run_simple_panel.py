"""Run bounded simple-rate comparisons and retain failed numerical checks."""

import argparse
import subprocess
from pathlib import Path
from time import perf_counter

import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--variants", nargs="+", default=["baseline", "rain_daylight"])
parser.add_argument("--variance-power", type=float, choices=[1, 1.5], default=1)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(args.input / "manifest.csv")
status, diagnostics, predictions = [], [], []
started = perf_counter()
for variant in args.variants:
    for context in manifest.itertuples():
        folder = args.out / variant / context.key
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "run.log").open("w") as log:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/research/fit_simple_rate.py",
                    "--input",
                    str(args.input),
                    "--out",
                    str(folder),
                    "--variant",
                    variant,
                    "--keys",
                    context.key,
                    "--select-smoothing",
                    "--variance-power",
                    str(args.variance_power),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        status.append(dict(key=context.key, variant=variant, passed=result.returncode == 0))
        if result.returncode == 0:
            diagnostics.append(pd.read_csv(folder / "diagnostics.csv"))
            output = pd.read_csv(folder / "predictions.csv")
            output["variant"] = variant
            predictions.append(output)
pd.DataFrame(status).to_csv(args.out / "status.csv", index=False)
pd.concat(diagnostics, ignore_index=True).to_csv(args.out / "diagnostics.csv", index=False)
pd.concat(predictions, ignore_index=True).to_csv(args.out / "predictions.csv", index=False)
print(f"Completed {len(status)} attempts in {perf_counter() - started:.1f} seconds.")
print(pd.DataFrame(status).groupby("variant").passed.agg(["sum", "count"]).to_string())
