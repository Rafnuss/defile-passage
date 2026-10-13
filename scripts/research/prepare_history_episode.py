"""Prepare a bounded episode screen on historical gaps and current recent masks."""

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/history-episode"
INPUT = OUT / "input"
DESIGN = OUT / "design"
INPUT.mkdir(parents=True, exist_ok=True)
DESIGN.mkdir(parents=True, exist_ok=True)
history = pd.read_csv(ROOT / "logs/historical-counts/observations.csv", low_memory=False)
history = history[history.training_eligible]
parts = pd.read_csv(ROOT / "logs/historical-counts/components.csv")
records = []
recent = ROOT / "logs/history-diagnosis/current-recent/input"
for context in pd.read_csv(recent / "manifest.csv").itertuples():
    obs = pd.read_csv(recent / f"{context.key}_observations.csv")
    rows = pd.read_csv(recent / f"{context.key}_components.csv")
    old = history[history.english_name.eq(context.english_name)].copy()
    old_parts = parts[parts.observation_id.isin(old.observation_id)].copy()
    offset = int(obs.observation_id.max()) + 1
    old["observation_id"] += offset
    old_parts["observation_id"] += offset
    old["hidden"], old_parts["hidden"] = False, False
    combined = pd.concat([obs, old], ignore_index=True)
    combined_parts = pd.concat([rows, old_parts], ignore_index=True)
    for frame in [combined, combined_parts]:
        frame["date"] = pd.to_datetime(frame.date, format="ISO8601").dt.strftime("%Y-%m-%d")
    pd.testing.assert_series_equal(
        combined[combined.hidden].groupby("date")["count"].sum(),
        obs[obs.hidden].groupby("date")["count"].sum(),
    )
    assert combined.observation_id.is_unique
    exposure = combined_parts.groupby("observation_id").fraction.sum()
    assert np.allclose(exposure.reindex(combined.observation_id), combined.exposure_hours)
    key = "recent__" + context.key
    combined.to_csv(INPUT / f"{key}_observations.csv", index=False)
    combined_parts.to_csv(INPUT / f"{key}_components.csv", index=False)
    records.append(
        dict(key=key, english_name=context.english_name, fold=context.fold, task="recent")
    )
pd.DataFrame(records).to_csv(INPUT / "manifest.csv", index=False)
subprocess.run(
    ["Rscript", "scripts/research/prepare_historical_transfer.R", str(INPUT), str(DESIGN)],
    check=True,
)
historical = ROOT / "logs/historical-counts/design"
for context in pd.read_csv(historical / "manifest.csv").query("fold == 2").itertuples():
    key = "historical__" + context.key
    for suffix in [
        "observations",
        "components",
        "year_weather_X",
        "year_weather_penalty",
        "year_weather_terms",
    ]:
        (DESIGN / f"{key}_{suffix}.csv").write_bytes(
            (historical / f"{context.key}_{suffix}.csv").read_bytes()
        )
    records.append(
        dict(key=key, english_name=context.english_name, fold=context.fold, task="historical")
    )
pd.DataFrame(records).to_csv(DESIGN / "manifest.csv", index=False)
subprocess.run(["Rscript", "scripts/research/prepare_history_episode.R", str(DESIGN)], check=True)
print(
    "Prepared 10 historical seven-day tasks and 30 current recent tasks with historical training."
)
