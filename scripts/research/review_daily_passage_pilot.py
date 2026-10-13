"""Review numerical/runtime checks only; no hidden-count accuracy assessment."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/daily-passage-pilot")
manifest = pd.read_csv(OUT / "manifest.csv")
failures = pd.read_csv(OUT / "failures.csv")
rows, support = [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    if not (folder / "diagnostics.csv").exists():
        continue
    rows.append(pd.read_csv(folder / "diagnostics.csv"))
    weather = pd.read_csv(folder / "weather_support.csv")
    weather["key"] = context.key
    support.append(weather)
diagnostics = pd.concat(rows, ignore_index=True)
complete = len(diagnostics) == len(manifest) == 8 and failures.empty
diagnostics.to_csv(OUT / "diagnostics.csv", index=False)
pd.concat(support, ignore_index=True).to_csv(OUT / "weather_support.csv", index=False)
checks = pd.DataFrame(
    [
        dict(gate="all_eight_contexts_complete", passed=complete),
        dict(gate="gradient_below_0.001", passed=diagnostics.gradient.lt(0.001).all()),
        dict(gate="derivative_below_0.001", passed=diagnostics.derivative_error.lt(0.001).all()),
        dict(gate="exact_year_centering", passed=diagnostics.center_error.lt(1e-9).all()),
        dict(gate="objective_decreases", passed=diagnostics.objective_decreases.all()),
        dict(
            gate="baseline_reproduction",
            passed=diagnostics.replay_rate_error.lt(1e-5).all()
            and diagnostics.replay_loss_error.lt(1e-7).all()
            and diagnostics.zero_state_loss.lt(1e-7).all(),
        ),
        dict(gate="median_final_5_seconds", passed=diagnostics.final_seconds.median() <= 5),
        dict(gate="median_ratio_5", passed=diagnostics.runtime_ratio.median() <= 5),
        dict(
            gate="whole_context_60_seconds",
            passed=complete and diagnostics.whole_context_seconds.lt(60).all(),
        ),
    ]
)
checks.to_csv(OUT / "acceptance.csv", index=False)
print(
    diagnostics[
        [
            "key",
            "gradient",
            "derivative_error",
            "iterations",
            "message",
            "final_seconds",
            "runtime_ratio",
            "effective_df",
            "effective_df_mc_se",
        ]
    ].to_string(index=False)
)
print(checks.to_string(index=False))
print("Median final seconds:", diagnostics.final_seconds.median())
print("Median paired runtime ratio:", diagnostics.runtime_ratio.median())
print("Maximum context seconds:", diagnostics.whole_context_seconds.max())
print(
    "Shared Schur condition range:",
    diagnostics.scaled_shared_schur_condition.agg(["min", "max"]).to_dict(),
)
print(
    "Conditional daily information condition range:",
    diagnostics.conditional_daily_information_condition.agg(["min", "max"]).to_dict(),
)
assert np.isfinite(diagnostics.effective_df).all()
