"""Fixed numerical-only gate before the count-balanced core comparison."""

import subprocess
import sys
from pathlib import Path

import pandas as pd

CONTEXT_SECONDS = 60
OUT = Path("logs/count-balanced-pilot")
OUT.mkdir(parents=True, exist_ok=True)
KEYS = [
    "historical__Common_Buzzard_fold2",
    "historical__Eurasian_Sparrowhawk_fold2",
    "historical__European_Honey_Buzzard_fold2",
    "historical__White_Stork_fold2",
    "historical__Grey_Heron_fold2",
    "recent__Common_Buzzard_fold0",
    "recent__White_Stork_fold2",
    "recent__Grey_Heron_fold2",
]
failures = []
for key in KEYS:
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
                    "1",
                    "--numerical-only",
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
checks = pd.concat([pd.read_csv(OUT / f"fits/{key}/diagnostics.csv") for key in KEYS])
checks.to_csv(OUT / "checks.csv", index=False)
wide = checks.pivot(index="key", columns="method", values="final_seconds")
ratio = wide.weather_daily / wide.weather_mean
passed = (
    not failures
    and len(checks) == 16
    and checks.gradient.lt(0.001).all()
    and checks.derivative_error.lt(0.001).all()
    and checks.center_error.lt(1e-9).all()
    and checks.retained_count_error.abs().lt(0.001).all()
    and wide.weather_daily.median() <= 5
    and ratio.median() <= 5
)
pd.DataFrame(
    [
        dict(
            passed=passed,
            contexts=len(KEYS) - len(failures),
            median_final_seconds=wide.weather_daily.median(),
            median_paired_ratio=ratio.median(),
            max_gradient=checks.gradient.max(),
            max_derivative=checks.derivative_error.max(),
            max_count_error=checks.retained_count_error.abs().max(),
        )
    ]
).to_csv(OUT / "gate.csv", index=False)
print(checks.to_string(index=False))
print("Numerical pilot gate:", passed)
assert passed
