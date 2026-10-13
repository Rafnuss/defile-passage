"""Check count-support eligibility and exact intact-interval exposure."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/historical-counts")
obs = pd.read_csv(OUT / "observations.csv", low_memory=False)
parts = pd.read_csv(OUT / "components.csv")
issues = pd.read_csv(OUT / "count_support_issues.csv")
assert obs[~obs.scope_verified & obs.recorded_count.isna()]["count"].isna().all()
assert not obs[obs.unknown_support.eq(True)].training_eligible.any()
assert np.array_equal(
    obs.loc[obs.recorded_count.notna(), "count"],
    obs.loc[obs.recorded_count.notna(), "recorded_count"],
)
assert parts.observation_id.isin(obs.observation_id).all()
assert np.allclose(
    parts.groupby("observation_id").fraction.sum().reindex(obs.observation_id), obs.exposure_hours
)
assert parts[["rain_mm", "wind_u_m_s", "wind_v_m_s", "tau"]].notna().all().all()
assert not obs.duplicated(["survey_id", "taxon_id"]).any()
print(
    "Intact totals preserved, unknown absences remain unknown, unsupported species-dates excluded, and exposure/weather reconciled."
)
print(
    "Species-surveys:",
    len(obs),
    "; components:",
    len(parts),
    "; eligible:",
    obs.training_eligible.sum(),
)
print(
    "Support issues:",
    len(issues),
    "; affected species-dates:",
    issues[["english_name", "date"]].drop_duplicates().shape[0],
)
