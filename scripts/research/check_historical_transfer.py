"""Check matched information, indivisible masks, and sparse-year calibration inputs."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/historical-transfer")
manifest = pd.read_csv(OUT / "input/manifest.csv")
checks = []
for context in manifest[manifest.resolution.eq("hour")].itertuples():
    hour = pd.read_csv(OUT / f"input/{context.key}_components.csv")
    coarse_key = context.key.removesuffix("_hour") + "_survey"
    coarse = pd.read_csv(OUT / f"input/{coarse_key}_components.csv")
    observations = pd.read_csv(OUT / f"input/{coarse_key}_observations.csv")
    assert np.array_equal(hour.hidden, coarse.hidden)
    assert np.array_equal(hour["count"], coarse["count"])
    assert np.array_equal(hour.fraction, coarse.fraction)
    assert not hour.loc[hour.year.ne(context.target_year), "hidden"].any()
    assert hour.loc[hour.year.eq(context.target_year), "hidden"].any()
    reconstructed = coarse.groupby("observation_id", sort=False)["count"].sum()
    assert np.array_equal(reconstructed.to_numpy(), observations["count"].to_numpy())
    assert not observations[observations.hidden].resolution.eq("survey").any()
    for _, group in coarse[coarse.observation_id.ge(len(coarse))].groupby("observation_id"):
        assert group.date.nunique() == 1
        assert np.array_equal(group.start.to_numpy()[1:], group.end.to_numpy()[:-1])
    target = hour[hour.year.eq(context.target_year)]
    daily = target.groupby("date").agg(
        hours=("fraction", "sum"),
        hidden_hours=("fraction", lambda x: x[target.loc[x.index, "hidden"]].sum()),
    )
    checks.append(
        dict(
            key=context.key,
            retained_fraction=1
            - target.loc[target.hidden, "fraction"].sum() / target.fraction.sum(),
            wholly_hidden_days=int(daily.hidden_hours.eq(daily.hours).sum()),
            partial_days=int(
                (daily.hidden_hours.gt(0) & daily.hidden_hours.lt(daily.hours)).sum()
            ),
            retained_dates=int(daily.hidden_hours.lt(daily.hours).sum()),
        )
    )
pd.DataFrame(checks).to_csv(OUT / "mask_checks.csv", index=False)
print(
    f"{len(checks)} paired contexts passed; masks preserve matching counts/exposure and never divide observations."
)
