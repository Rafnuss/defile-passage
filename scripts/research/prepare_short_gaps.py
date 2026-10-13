"""Reuse exact short-gap targets while allowing retained hours into the mean fit."""

from pathlib import Path

import pandas as pd
from simple_rate_prediction import short_gap_mask

for panel in ["priority", "passerines"]:
    source = Path(f"logs/gap-validation-input-{panel}")
    out = Path(f"logs/short-gaps-input-{panel}")
    out.mkdir(exist_ok=True)
    manifest = pd.read_csv(source / "manifest.csv")
    combined = []
    for context in manifest.itertuples():
        rows = pd.read_csv(source / f"{context.key}_components.csv")
        rows["target_day"] = rows.hidden
        rows["short_gap"] = short_gap_mask(rows)
        rows["hidden"] = rows.target_day & rows.short_gap
        assert (
            rows.groupby("date")
            .apply(lambda x: x.hidden.sum() in [0, 3], include_groups=False)
            .all()
        )
        rows.to_csv(out / f"{context.key}_components.csv", index=False)
        observations = pd.read_csv(source / f"{context.key}_observations.csv")
        observations["hidden"] = rows.hidden
        observations.to_csv(out / f"{context.key}_observations.csv", index=False)
        if context.fold == 0:
            rows["block_fold"] = rows.block_fold.where(rows.short_gap, -1)
            combined.append(rows)
    manifest.to_csv(out / "manifest.csv", index=False)
    pd.concat(combined, ignore_index=True).to_csv(out / "validation_masks.csv", index=False)
