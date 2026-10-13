"""Reuse the original benchmark's exact whole-day training and test intervals."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--panel", required=True, choices=["priority", "passerines"])
args = parser.parse_args()
source = Path(f"logs/hourly-weather-{args.panel}")
out = Path(f"logs/simple-gaps-input-{args.panel}")
out.mkdir(exist_ok=True)
manifest = pd.read_csv(source / "manifest.csv").query("fold < 3").copy()
manifest["heldout_year"] = np.nan
for context in manifest.itertuples():
    key = context.key
    training = pd.read_csv(source / f"{key}_train.csv").assign(hidden=False)
    testing = pd.read_csv(source / f"{key}_test.csv").assign(hidden=True)
    rows = pd.concat([training, testing], ignore_index=True)
    rows["observation_id"] = np.arange(len(rows))
    assert not rows.groupby("date").hidden.nunique().gt(1).any()
    assert not rows.duplicated(["start", "end"]).any()
    observations = rows[
        [
            "observation_id",
            "date",
            "start",
            "end",
            "count",
            "english_name",
            "exposure_hours",
            "hidden",
        ]
    ].copy()
    observations["resolution"] = "hour"
    rows["fraction"] = rows.exposure_hours
    observations.to_csv(out / f"{key}_observations.csv", index=False)
    rows.to_csv(out / f"{key}_components.csv", index=False)
manifest.to_csv(out / "manifest.csv", index=False)
