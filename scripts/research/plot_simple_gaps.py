"""Plot per-species full-day errors relative to the original benchmark."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, required=True)
args = parser.parse_args()
scores = pd.read_csv(args.input / "species_scores.csv")
names = sorted(scores.english_name.unique())
fig, axes = plt.subplots(1, 2, figsize=(11, 7), sharey=True)
for ax, weather in zip(axes, ["dry", "wet"]):
    frame = scores[scores.weather.eq(weather)].set_index("english_name").reindex(names)
    colors = np.where(frame.mae_ratio < 1, "#1976b5", "#b54c26")
    ax.scatter(frame.mae_ratio, np.arange(len(names)), color=colors)
    ax.axvline(1, color="grey", linewidth=1)
    ax.set_title(f"{weather.capitalize()} hidden days")
    ax.set_xlabel("Mean absolute error / original benchmark error")
    ax.set_xlim(left=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.2)
axes[0].set_yticks(np.arange(len(names)), names)
axes[0].invert_yaxis()
fig.suptitle("Whole-day gaps: values below 1 favor the simple weather model")
fig.tight_layout()
fig.savefig(args.input / "benchmark_comparison.png", dpi=180)
