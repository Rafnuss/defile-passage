"""Plot held-out hourly passage rates across observed daylight coordinates."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--prefix", default="coherent-wide-time")
parser.add_argument("--out", type=Path, default=root / "logs/wide-time-refit-review")
args = parser.parse_args()
folder = args.out
rows = pd.read_csv(root / f"logs/{args.prefix}-priority-year/held_out_intervals.csv")
old = pd.read_csv(root / "logs/coherent-intervals-priority-year/held_out_intervals.csv")
rows = rows.merge(
    old[["english_name", "fold", "observation_id", "predicted"]],
    on=["english_name", "fold", "observation_id"],
    suffixes=("", "_frozen"),
    validate="one_to_one",
)
fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
for ax, species in zip(axes, ["Great Cormorant", "Common Wood Pigeon"]):
    data = rows[
        rows.english_name.eq(species) & rows.fold.eq(8) & rows.resolution.eq("hour")
    ].copy()
    components = pd.read_csv(
        root / f'logs/mixed-design-priority-year/{species.replace(" ","_")}_fold8_components.csv'
    )
    data = data.merge(
        components.groupby("observation_id", as_index=False).tau.mean(),
        on="observation_id",
        validate="one_to_one",
    )
    data["bin"] = np.floor(data.tau * 20) / 20 + 0.025
    bins = data.groupby("bin", as_index=False)[
        ["count", "predicted", "predicted_frozen", "exposure_hours"]
    ].sum()
    for column, label in [
        ("count", "Observed"),
        ("predicted", "Refitted time"),
        ("predicted_frozen", "Frozen time"),
    ]:
        ax.plot(bins.bin, bins[column] / bins.exposure_hours, marker=".", label=label)
    ax.axvline(0, color="grey", linestyle=":", linewidth=1)
    ax.axvline(1, color="grey", linestyle=":", linewidth=1)
    ax.set(
        title=f"{species}, held-out 2025",
        xlabel="Civil-daylight coordinate",
        ylabel="Birds per observed hour",
        yscale="symlog",
    )
    ax.spines[["top", "right"]].set_visible(False)
axes[0].legend(frameon=False)
folder.mkdir(parents=True, exist_ok=True)
fig.savefig(folder / "time_refit_2025.png", dpi=200)
