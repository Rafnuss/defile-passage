"""Run the forty-context daily-passage screen with fixed process limits."""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

OUT = Path("logs/daily-passage")
CONTEXT_SECONDS = 60
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, default=OUT)
parser.add_argument("--variance-power", type=float, choices=[1, 1.5], default=1.5)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
OUT = args.out
OUT.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv("logs/history-episode/design/manifest.csv")
if args.shard[0] == 0:
    (OUT / "design").mkdir(parents=True, exist_ok=True)
    manifest.to_csv(OUT / "design/manifest.csv", index=False)
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
failures = []
for key in manifest.key:
    with (OUT / f"{key}.log").open("w") as log:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/research/run_daily_passage.py",
                    "--key",
                    key,
                    "--out",
                    str(OUT),
                    "--variance-power",
                    str(args.variance_power),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=CONTEXT_SECONDS,
            )
            if result.returncode:
                failures.append(dict(key=key, reason=f"exit_{result.returncode}"))
        except subprocess.TimeoutExpired:
            failures.append(dict(key=key, reason="context_60_second_limit"))
pd.DataFrame(failures, columns=["key", "reason"]).to_csv(
    OUT / f"failures-{args.shard[0]}.csv", index=False
)
print("Shard finished; failed contexts:", len(failures), flush=True)
