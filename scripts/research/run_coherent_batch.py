"""Run independent mixed-scale contexts concurrently, then combine completed caches."""

import argparse
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--panel", default="priority")
parser.add_argument("--workers", type=int, default=3)
parser.add_argument("--refit-time", action="store_true")
parser.add_argument("--extended-time", action="store_true")
parser.add_argument("--full-reference", action="store_true")
parser.add_argument("--draws", type=int, default=300)
parser.add_argument("--prefix", default="coherent-intervals")
parser.add_argument("--exclude-keys", nargs="*", default=[])
parser.add_argument("--no-aggregate", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
suffix = "" if args.full_reference else "-year"
output_suffix = "-full" if args.full_reference else suffix
folder = root / f"logs/{args.prefix}-{args.panel}{output_suffix}"
warm_prefix = "pooled-full" if args.full_reference else "pooled-activity"
folder.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(root / f"logs/mixed-design-{args.panel}{suffix}/manifest.csv")
keys = [
    key
    for key in manifest.key
    if key not in args.exclude_keys and not (folder / f"{key}_diagnostics.csv").exists()
]


def run(key):
    output = folder / "contexts" / key
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "uv",
        "run",
        "python",
        "scripts/research/fit_coherent_intervals.py",
        "--input",
        f"logs/mixed-design-{args.panel}{suffix}",
        "--prepared",
        f"logs/hourly-weather-{args.panel}{suffix}",
        "--warm-start",
        f"logs/{warm_prefix}-{args.panel}{suffix}",
        "--out",
        str(output),
        "--keys",
        key,
        "--resume",
    ]
    command.extend(["--draws", str(args.draws)])
    if args.refit_time:
        command.append("--refit-time")
    if args.extended_time:
        command.append("--extended-time")
    with (output / "run.log").open("w") as log:
        subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
    for path in output.glob(f"{key}_*"):
        shutil.copy2(path, folder / path.name)


with ThreadPoolExecutor(max_workers=args.workers) as executor:
    list(executor.map(run, keys))
if args.no_aggregate:
    print(f"{args.panel}: selected contexts completed")
    raise SystemExit(0)
pd.concat(
    [pd.read_csv(folder / f"{key}_predictions.csv") for key in manifest.key], ignore_index=True
).to_csv(folder / "held_out_intervals.csv", index=False)
pd.concat(
    [pd.read_csv(folder / f"{key}_diagnostics.csv") for key in manifest.key], ignore_index=True
).to_csv(folder / "fit_diagnostics.csv", index=False)
print(f"{args.panel}: all {len(manifest)} contexts completed")
