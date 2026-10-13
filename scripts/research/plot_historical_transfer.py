"""Show seasonal reconstruction error separately from day-level gap error."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path("logs/historical-transfer")
season = pd.read_csv(OUT / "season_scores.csv")
gap = pd.read_csv(OUT / "group_gap_scores.csv")
season = season[season.assessment_group.eq("core_large_birds")]
gap = gap[gap.assessment_group.eq("core_large_birds") & gap.weather.eq("all")]
scenarios = ["early", "staff", "live", "weather"]
labels = ["2007 attendance", "2015 attendance", "2021 attendance", "Weather gaps"]
methods = ["original_episode", "weather_mean", "weather_retained"]
colors = ["#666666", "#0072B2", "#009E73"]
legend = ["Original benchmark", "Weather model", "Weather + retained update"]
fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
for column, resolution in enumerate(["hour", "survey"]):
    for row, (frame, metric, ylabel) in enumerate(
        [
            (season, "mean_absolute_relative_bias", "Mean absolute seasonal error (%)"),
            (gap, "absolute_error", "Mean absolute daily gap error (birds)"),
        ]
    ):
        for index, (method, color, name) in enumerate(zip(methods, colors, legend)):
            sample = frame[frame.resolution.eq(resolution) & frame.method.eq(method)].set_index(
                "scenario"
            )
            values = sample.reindex(scenarios)[metric].to_numpy() * (100 if row == 0 else 1)
            axes[row, column].bar(
                np.arange(4) + (index - 1) * 0.24, values, width=0.23, color=color, label=name
            )
        axes[row, column].set_ylabel(ylabel)
        axes[row, column].spines[["top", "right"]].set_visible(False)
        axes[row, column].set_axisbelow(True)
        axes[row, column].grid(axis="y", alpha=0.2)
    axes[0, column].set_title(
        "Target-year hourly counts" if resolution == "hour" else "Target-year survey totals"
    )
    axes[1, column].set_xticks(range(4), labels, rotation=15)
axes[0, 0].legend(frameon=False, fontsize=9)
fig.suptitle("Historical coverage transfer: ten core large-bird species")
fig.text(
    0.5,
    0.015,
    "Equal-species averages across four modern years; scored observed windows only. Pre-1993 stress test excluded here.",
    ha="center",
    fontsize=9,
)
fig.tight_layout(rect=(0, 0.045, 1, 0.96))
fig.savefig(OUT / "core_comparison.png", dpi=180)
fig.savefig(OUT / "core_comparison.pdf")
