"""Run all eight fixed numerical contexts before reviewing their saved checks."""

import subprocess
import sys
from pathlib import Path

import pandas as pd

OUT = Path("logs/daily-passage-pilot")
SOURCE = Path("logs/history-episode")
SPECIES = ["Common Buzzard", "European Honey Buzzard", "Great Cormorant", "White Stork"]
CONTEXT_SECONDS = 60
OUT.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
manifest = manifest[
    manifest.english_name.isin(SPECIES)
    & (
        (manifest.task.eq("historical") & manifest.fold.eq(2))
        | (manifest.task.eq("recent") & manifest.fold.eq(0))
    )
]
assert len(manifest) == 8
manifest.to_csv(OUT / "manifest.csv", index=False)
failures = []
for key in manifest.key:
    with (OUT / f"{key}.log").open("w") as log:
        try:
            result = subprocess.run(
                [sys.executable, "scripts/research/run_daily_passage_pilot.py", "--key", key],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=CONTEXT_SECONDS,
            )
            if result.returncode:
                failures.append(dict(key=key, reason=f"exit_{result.returncode}"))
        except subprocess.TimeoutExpired:
            failures.append(dict(key=key, reason="context_60_second_limit"))
pd.DataFrame(failures, columns=["key", "reason"]).to_csv(OUT / "failures.csv", index=False)
print("Fixed numerical batch finished; failed contexts:", len(failures), flush=True)
