"""Freeze count-independent 1/3/7-day masks on the existing recent hourly data.

These are new internal stress-test masks, not new observations: every date has already appeared in
a development holdout. Calendar gaps hide all eligible effort, including observed zeros.
"""

from pathlib import Path

import numpy as np
import pandas as pd

CYCLE_DAYS = 21
# Shift the seven-day gaps off the original week boundaries; rotate placement between years.
GAPS = {0: (0, 1), 1: (5, 3), 2: (12, 7)}
PREFIX = "gap-validation"

for panel in ["priority", "passerines"]:
    source = Path(f"data/hourly-weather-{panel}")
    out = Path(f"logs/{PREFIX}-input-{panel}")
    out.mkdir(parents=True, exist_ok=True)
    rows = pd.read_csv(source / "validation_masks.csv")
    phase = (rows.doy - 3 + 4 * (rows.year - rows.year.min())) % CYCLE_DAYS
    rows["block_fold"] = -1
    for fold, (start, length) in GAPS.items():
        rows.loc[phase.between(start, start + length - 1), "block_fold"] = fold
    rows["hidden_hours"] = False
    rows.to_csv(out / "validation_masks.csv", index=False)
    manifest = []
    for species, sample in rows.groupby("english_name"):
        sample = sample.copy().reset_index(drop=True)
        sample["observation_id"] = np.arange(len(sample))
        sample["fraction"] = sample.exposure_hours
        for fold, (_, length) in GAPS.items():
            key = species.replace(" ", "_") + f"_fold{fold}"
            components = sample.assign(hidden=sample.block_fold.eq(fold))
            observations = components[
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
            ].assign(resolution="hour")
            assert not components.groupby("date").hidden.nunique().gt(1).any()
            assert not components.duplicated(["start", "end"]).any()
            components.to_csv(out / f"{key}_components.csv", index=False)
            observations.to_csv(out / f"{key}_observations.csv", index=False)
            manifest.append(
                dict(
                    key=key, english_name=species, fold=fold, gap_days=length, heldout_year=np.nan
                )
            )
    pd.DataFrame(manifest).to_csv(out / "manifest.csv", index=False)
    days = rows.drop_duplicates(["english_name", "date"])
    days[["english_name", "date", "year", "doy", "block_fold"]].to_csv(
        out / "calendar_masks.csv", index=False
    )
    print(panel, days.groupby("block_fold").size().to_dict())
