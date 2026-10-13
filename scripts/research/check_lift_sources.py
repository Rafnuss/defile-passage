"""Audit new ERA5 source timing against unchanged rain and radiation inputs."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/era5-lift")
weather = pd.read_csv(OUT / "weather.csv", index_col=0)
raw = pd.read_csv(OUT / "raw_hourly.csv", index_col=0)
weather.index = pd.to_datetime(weather.index, utc=True)
raw.index = pd.to_datetime(raw.index, utc=True)
month_day = weather.index.strftime("%m-%d")
season = (month_day >= "07-18") & (month_day <= "11-18")
alignment, comparisons = [], []
for name, source, scale in [("rain_mm", "tp", 1000), ("radiation_w_m2", "ssrd", 1 / 3600)]:
    aligned = (raw[source].shift(-1) * scale).reindex(weather.index)
    assert np.isfinite(aligned).all()
    difference = aligned - weather[name]
    pd.DataFrame(dict(year=weather.index.year, difference=abs(difference))).groupby(
        "year"
    ).difference.mean().to_csv(OUT / f"{name}_source_year.csv")
    correlation = aligned[season].corr(weather.loc[season, name])
    assert correlation > 0.99
    comparisons.append(
        dict(
            variable=name,
            season_correlation=correlation,
            season_mae=abs(difference[season]).mean(),
            season_maximum_difference=abs(difference[season]).max(),
        )
    )
    losses = []
    for lag in [-1, 0, 1]:
        loss = abs(aligned.shift(lag) - weather[name]).mean()
        losses.append(loss)
        alignment.append(dict(variable=name, extra_shift_hours=lag, mae=loss))
    assert np.argmin(losses) == 1
pd.DataFrame(alignment).to_csv(OUT / "source_alignment.csv", index=False)
pd.DataFrame(comparisons).to_csv(OUT / "source_season_comparison.csv", index=False)
print(pd.DataFrame(comparisons).to_string(index=False))
print("Both source controls pass the correlation and zero-additional-shift checks.")
