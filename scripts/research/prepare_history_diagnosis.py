"""Isolate historical training and count resolution on frozen recent holdouts."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/history-diagnosis"
INPUT = OUT / "input"
INPUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / "logs/simple-gaps-input-priority"
core = pd.read_csv(ROOT / "scripts/research/historical_core_scope.tsv").english_name
manifest = pd.read_csv(SOURCE / "manifest.csv")
manifest = manifest[manifest.english_name.isin(core)]
history = pd.read_csv(ROOT / "logs/historical-counts/observations.csv", low_memory=False)
history = history[history.training_eligible].copy()
parts = pd.read_csv(ROOT / "logs/historical-counts/components.csv", low_memory=False)
records, audit = [], []
for context in manifest.itertuples():
    recent = pd.read_csv(SOURCE / f"{context.key}_observations.csv").assign(source="recent")
    recent_parts = pd.read_csv(SOURCE / f"{context.key}_components.csv").assign(source="recent")
    recent["year"] = pd.to_datetime(recent.date).dt.year
    original_truth = recent[recent.hidden].groupby("date")["count"].sum()
    for arm in ["recent", "recent_coarse", "late_history", "all_history"]:
        obs, rows = recent.copy(), recent_parts.copy()
        if arm == "recent_coarse":
            # Aggregate training only; hidden hours and their truth remain untouched.
            obs = obs.sort_values(["date", "start"]).copy()
            obs = obs.merge(
                rows[["observation_id", "survey_id"]], on="observation_id", validate="one_to_one"
            )
            obs["group"] = (
                obs.hidden
                | obs.hidden.shift(fill_value=False)
                | obs.survey_id.ne(obs.survey_id.shift())
                | obs.start.ne(obs.end.shift())
            ).cumsum()
            rows = rows.merge(
                obs[["observation_id", "group"]], on="observation_id", validate="one_to_one"
            )
            obs = (
                obs.groupby("group", as_index=False)
                .agg(
                    date=("date", "first"),
                    start=("start", "first"),
                    end=("end", "last"),
                    count=("count", "sum"),
                    english_name=("english_name", "first"),
                    exposure_hours=("exposure_hours", "sum"),
                    hidden=("hidden", "first"),
                    year=("year", "first"),
                    source=("source", "first"),
                )
                .rename(columns={"group": "observation_id"})
            )
            obs["resolution"] = np.where(obs.hidden, "hour", "survey")
            rows["observation_id"] = rows["group"]
            rows = rows.drop(columns="group")
        if arm in ["late_history", "all_history"]:
            old = history[history.english_name.eq(context.english_name)].copy()
            if arm == "late_history":
                old = old[old.year.ge(2014)].copy()
            old_parts = parts[parts.observation_id.isin(old.observation_id)].copy()
            offset = int(obs.observation_id.max()) + 1
            old["observation_id"] += offset
            old_parts["observation_id"] += offset
            old["source"], old["hidden"] = "historical", False
            old_parts["source"], old_parts["hidden"] = "historical", False
            obs = pd.concat([obs, old], ignore_index=True)
            rows = pd.concat([rows, old_parts], ignore_index=True)
        obs["date"] = pd.to_datetime(obs.date, format="ISO8601").dt.strftime("%Y-%m-%d")
        rows["date"] = pd.to_datetime(rows.date, format="ISO8601").dt.strftime("%Y-%m-%d")
        obs = obs[
            [
                "observation_id",
                "date",
                "start",
                "end",
                "count",
                "english_name",
                "exposure_hours",
                "hidden",
                "resolution",
                "source",
                "year",
            ]
        ]
        rows = rows[
            [
                "observation_id",
                "date",
                "slot_start",
                "start",
                "end",
                "fraction",
                "rain_mm",
                "wind_u_m_s",
                "wind_v_m_s",
                "tau",
                "year",
                "doy",
                "hidden",
                "source",
            ]
        ]
        truth = obs[obs.hidden].groupby("date")["count"].sum()
        pd.testing.assert_series_equal(truth, original_truth, check_dtype=False)
        assert not obs.observation_id.duplicated().any()
        exposure = rows.groupby("observation_id").fraction.sum().reindex(obs.observation_id)
        assert np.allclose(exposure, obs.exposure_hours)
        assert obs.loc[obs.source.eq("recent"), "count"].sum() == recent["count"].sum()
        key = context.key + "__" + arm
        obs.to_csv(INPUT / f"{key}_observations.csv", index=False)
        rows.to_csv(INPUT / f"{key}_components.csv", index=False)
        records.append(
            dict(
                key=key,
                original_key=context.key,
                english_name=context.english_name,
                fold=context.fold,
                arm=arm,
                heldout_year=np.nan,
            )
        )
        audit.append(
            dict(
                key=key,
                training_intervals=int((~obs.hidden).sum()),
                historical_intervals=int(obs.source.eq("historical").sum()),
                heldout_hours=obs.loc[obs.hidden, "exposure_hours"].sum(),
                heldout_birds=obs.loc[obs.hidden, "count"].sum(),
            )
        )
pd.DataFrame(records).to_csv(INPUT / "manifest.csv", index=False)
pd.DataFrame(audit).to_csv(OUT / "input_audit.csv", index=False)
files = list(SOURCE.glob("*_observations.csv")) + list(SOURCE.glob("*_components.csv"))
files += [
    ROOT / "logs/historical-counts/observations.csv",
    ROOT / "logs/historical-counts/components.csv",
]
(OUT / "sources.json").write_text(
    json.dumps({str(p): sha256(p.read_bytes()).hexdigest() for p in files}, indent=2) + "\n"
)
print(
    "Prepared",
    len(records),
    "contexts; identical recent held-out counts, hours and total recent birds.",
)
