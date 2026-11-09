"""Prepare matched historical holdouts within the adopted taxonomy and annual-record scope."""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_passage.export import in_window

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/historical-counts"
INPUT = OUT / "input"
INPUT.mkdir(exist_ok=True)
observations = pd.read_csv(OUT / "observations.csv", low_memory=False)
components = pd.read_csv(OUT / "components.csv")
assert (
    observations.training_eligible.any()
), "No historical species meet the adopted taxonomy start and annual-record panel rule."
observations = observations[observations.training_eligible].copy()
components = components[components.observation_id.isin(observations.observation_id)].copy()
observations["source"] = "historical"
recent = pd.read_csv(ROOT / "archive/mixed-weather-intervals/observations.csv")
recent = recent[
    recent.english_name.isin(observations.english_name)
    & in_window(pd.to_datetime(recent.date, format="ISO8601"))
].copy()
recent_components = pd.read_csv(ROOT / "archive/mixed-weather-intervals/hour_components.csv")
recent_components = recent_components[
    recent_components.observation_id.isin(recent.observation_id)
].copy()
recent["observation_id"] += int(components.observation_id.max()) + 1
recent_components["observation_id"] += int(components.observation_id.max()) + 1
recent["source"] = "recent"
recent["year"] = pd.to_datetime(recent.date, format="ISO8601").dt.year
recent_components = recent_components.merge(
    recent[["observation_id", "english_name"]], on="observation_id"
)
observations = pd.concat([observations, recent], ignore_index=True)
components = pd.concat([components, recent_components], ignore_index=True)
observations["date"] = pd.to_datetime(observations.date, format="ISO8601").dt.strftime("%Y-%m-%d")
components["date"] = pd.to_datetime(components.date, format="ISO8601").dt.strftime("%Y-%m-%d")
manifest = []
for species, sample in observations.groupby("english_name"):
    sample = sample.sort_values(["date", "start"]).copy()
    sample["observation_id_original"] = sample.observation_id
    sample["observation_id"] = np.arange(len(sample))
    parts = (
        components[components.english_name.eq(species)]
        .rename(columns={"observation_id": "observation_id_original"})
        .copy()
    )
    parts = parts.merge(
        sample[["observation_id_original", "observation_id"]], on="observation_id_original"
    ).sort_values(["date", "start"])
    phase = (
        pd.to_datetime(sample.date).dt.dayofyear
        - (
            pd.to_datetime(sample.date).dt.is_leap_year
            & pd.to_datetime(sample.date).dt.month.gt(2)
        )
        - 3
        + 4 * (sample.year - 1993)
    ) % 21
    short = pd.Series(False, index=sample.index)
    for _, day in sample[sample.source.eq("historical")].groupby("date"):
        run = (
            day.start.ne(day.end.shift())
            | day.exposure_hours.gt(1.5)
            | day.exposure_hours.shift().gt(1.5)
        ).cumsum()
        eligible = day[day.exposure_hours.le(1.5)]
        if len(eligible) == 0:
            continue
        counts = run.loc[eligible.index].value_counts()
        longest = eligible[run.loc[eligible.index].eq(counts.idxmax())]
        if len(longest) < 6:
            continue
        doy = int(pd.Timestamp(day.date.iloc[0]).dayofyear)
        position = [0, (len(longest) - 3) // 2, len(longest) - 3][doy % 3]
        short.loc[longest.index[position : position + 3]] = True
    for fold, start, length in [(0, 0, 1), (1, 5, 3), (2, 12, 7), (3, 0, 0)]:
        key = species.replace(" ", "_") + f"_fold{fold}"
        obs = sample.copy()
        obs["hidden"] = obs.source.eq("historical") & (
            short if fold == 3 else phase.between(start, start + length - 1)
        )
        part = parts.merge(obs[["observation_id", "hidden"]], on="observation_id")
        assert part.groupby("observation_id").hidden.nunique().eq(1).all()
        assert (~obs.hidden).groupby(obs.year).any().all()
        obs.to_csv(INPUT / f"{key}_observations.csv", index=False)
        part.to_csv(INPUT / f"{key}_components.csv", index=False)
        manifest.append(
            dict(key=key, english_name=species, fold=fold, gap_days=length, heldout_year=np.nan)
        )
pd.DataFrame(manifest).to_csv(INPUT / "manifest.csv", index=False)
print("Prepared", len(manifest), "actual-historical contexts.")
