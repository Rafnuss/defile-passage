"""Plot held-out hourly counts and rate predictions across time of day."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
frames = []
for panel in ["priority", "passerines"]:
    folder = root / f"logs/simple-cyclic_clock-panel-{panel}"
    predictions = pd.read_csv(folder / "predictions.csv")
    inputs = root / f"logs/simple-rate-all-design-{panel}"
    for context in pd.read_csv(inputs / "manifest.csv").itertuples():
        predicted = predictions[
            predictions.english_name.eq(context.english_name)
            & predictions.fold.eq(context.fold)
            & predictions.resolution.eq("hour")
        ]
        components = pd.read_csv(inputs / f"{context.key}_components.csv")
        components = components[components.observation_id.isin(predicted.observation_id)]
        frame = predicted.merge(
            components[["observation_id", "tau", "fraction"]],
            on="observation_id",
            validate="one_to_one",
        )
        frames.append(frame)
data = pd.concat(frames, ignore_index=True)
data["time_bin"] = np.floor(data.tau / 0.05) * 0.05 + 0.025
summary = (
    data.groupby(["english_name", "time_bin"])[["count", "predicted", "fraction"]]
    .sum()
    .reset_index()
)
out = root / "logs/simple-panel-review-cyclic_clock"
out.mkdir(exist_ok=True)
summary.to_csv(out / "time_profile.csv", index=False)
fig, axes = plt.subplots(4, 4, figsize=(15, 11), sharex=True)
for ax, (name, frame) in zip(axes.flat, summary.groupby("english_name")):
    ax.plot(frame.time_bin, frame["count"] / frame.fraction, color="black", label="Observed")
    ax.plot(frame.time_bin, frame.predicted / frame.fraction, color="#1976b5", label="Predicted")
    ax.axvline(0, color="grey", linewidth=0.6)
    ax.axvline(1, color="grey", linewidth=0.6)
    ax.set_title(name, fontsize=10)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
axes[0, 0].legend(frameon=False, fontsize=8)
fig.supxlabel("Time relative to civil dawn (0) and dusk (1)")
fig.supylabel("Birds per observed hour (symlog scale)")
fig.suptitle("Simple periodic rate model: held-out hourly observations, 2022–2025", fontsize=13)
fig.tight_layout()
fig.savefig(out / "hourly_time_profile.png", dpi=180)
