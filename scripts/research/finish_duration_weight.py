"""Finish pending duration contexts with a fixed wall-time limit and no solver retries."""

import subprocess
import sys
from pathlib import Path

import pandas as pd

OUT = Path("logs/duration-weight")
OUT.mkdir(parents=True, exist_ok=True)
CONTEXT_SECONDS = 60
manifest = pd.read_csv("logs/history-episode/design/manifest.csv")
failures = []
for key in manifest.key:
    completed = [
        (OUT / f"power-{power}/fits/{key}/diagnostics.csv").exists() for power in [0.25, 0.5]
    ]
    if all(completed):
        continue
    with (OUT / f"bounded-{key}.log").open("w") as log:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/research/run_duration_weight.py",
                    "--key",
                    key,
                    "--resume",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=CONTEXT_SECONDS,
            )
            if result.returncode:
                failures.append(dict(key=key, reason=f"exit_{result.returncode}"))
        except subprocess.TimeoutExpired:
            failures.append(dict(key=key, reason="context_60_second_limit"))
pd.DataFrame(failures, columns=["key", "reason"]).to_csv(OUT / "failures.csv", index=False)
print("Bounded completion finished; failures:", len(failures))
