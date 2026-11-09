"""Audit matched-window inputs and prepare current recent and historical weather ablations."""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage.export import in_window

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/history-diagnosis"
manifest = pd.read_csv(OUT / "input/manifest.csv").query("arm == 'recent'")
recent = pd.read_csv(ROOT / "archive/mixed-weather-intervals/observations.csv")
recent["date"] = pd.to_datetime(recent.date, format="ISO8601").dt.strftime("%Y-%m-%d")
recent = recent[in_window(pd.to_datetime(recent.date))].copy()
parts = pd.read_csv(ROOT / "archive/mixed-weather-intervals/hour_components.csv")
parts["date"] = pd.to_datetime(parts.date, format="ISO8601").dt.strftime("%Y-%m-%d")
current = OUT / "current-recent/input"
current.mkdir(parents=True, exist_ok=True)
records, audits = [], []
for context in manifest.itertuples():
    obs = recent[recent.english_name.eq(context.english_name)].copy()
    obs["year"] = pd.to_datetime(obs.date).dt.year
    doy = pd.to_datetime(obs.date).dt.dayofyear - (
        pd.to_datetime(obs.date).dt.is_leap_year & pd.to_datetime(obs.date).dt.month.gt(2)
    )
    obs["hidden"] = ((doy - 1) // 7 + obs.year - 2022) % 3 == context.fold
    obs["source"] = "recent"
    rows = (
        parts[parts.observation_id.isin(obs.observation_id)]
        .drop(columns="hidden", errors="ignore")
        .copy()
    )
    rows = rows.merge(obs[["observation_id", "hidden"]], on="observation_id")
    rows["source"] = "recent"
    original = pd.read_csv(
        ROOT / f"logs/simple-gaps-input-priority/{context.original_key}_observations.csv"
    )
    old_mask = original.groupby("date").hidden.first()
    common = obs[obs.date.isin(old_mask.index)]
    assert common.hidden.eq(common.date.map(old_mask)).all()
    old_window = original[in_window(pd.to_datetime(original.date))].copy()
    if context.fold == 0:
        a = (
            old_window.assign(year=pd.to_datetime(old_window.date).dt.year)
            .groupby("year")
            .agg(old_window_birds=("count", "sum"), old_window_hours=("exposure_hours", "sum"))
        )
        b = obs.groupby("year").agg(
            mixed_birds=("count", "sum"), mixed_hours=("exposure_hours", "sum")
        )
        audits.append(a.join(b).assign(english_name=context.english_name))
    obs.to_csv(current / f"{context.original_key}_observations.csv", index=False)
    rows.to_csv(current / f"{context.original_key}_components.csv", index=False)
    records.append(
        dict(
            key=context.original_key,
            english_name=context.english_name,
            fold=context.fold,
            heldout_year=np.nan,
        )
    )
pd.DataFrame(records).to_csv(current / "manifest.csv", index=False)
pd.concat(audits).reset_index().to_csv(OUT / "recent_matched_window_audit.csv", index=False)
# Remove weather columns only; retain the historical season/time basis and support.
clear = OUT / "historical-clear/design"
clear.mkdir(parents=True, exist_ok=True)
historical = ROOT / "logs/historical-counts/design"
manifest = pd.read_csv(historical / "manifest.csv").query("fold < 3")
for context in manifest.itertuples():
    key = context.key
    X = np.loadtxt(historical / f"{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(historical / f"{key}_year_weather_penalty.csv", delimiter=",")
    keep = [0, *range(2, 15), *range(18, X.shape[1])]
    np.savetxt(clear / f"{key}_year_clear_X.csv", X[:, keep], delimiter=",")
    np.savetxt(clear / f"{key}_year_clear_penalty.csv", P[np.ix_(keep, keep)], delimiter=",")
    terms = pd.read_csv(historical / f"{key}_year_weather_terms.csv").iloc[keep]
    terms.to_csv(clear / f"{key}_year_clear_terms.csv", index=False)
    for suffix in ["observations", "components"]:
        (clear / f"{key}_{suffix}.csv").write_bytes(
            (historical / f"{key}_{suffix}.csv").read_bytes()
        )
manifest.to_csv(clear / "manifest.csv", index=False)
print("Prepared 30 current recent comparisons and 30 historical weather-removal controls.")
