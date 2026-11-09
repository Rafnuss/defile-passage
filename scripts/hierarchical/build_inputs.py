"""The observations of the hierarchical line, built from the release in `data/raw/dataset/`.

Run from the repository root (after copying a release with `build_explore.py --dataset`): uv run
--with 'pyarrow<20' python scripts/hierarchical/build_inputs.py > logs/hierarchical/inputs.log

`survey_complete` decides a zero: every bird that passed during a complete survey is in its counts,
so a core species absent from it was counted at zero. A weather stop is a complete survey in which
no bird passed (`DECISIONS.md` -> weather stops are zero passage): its coverage counts, with zero
birds, and it is flagged `weather_stop` (left out of the time-of-day profile, as production does).

One observation per survey and species, 1993-2025, inside the season window. A Trektellen survey is
split into its clock hours when every bird of the species in it is timed to one hour (the dataset's
point times or single-hour intervals); otherwise it stays whole. A species-date with an entry the
dataset cannot place inside its survey, or with presence only, is unknown and left out. Components
split each observation at clock hours: `fraction` (hours), `tau` (position between civil dawn and
dusk) and `doy` (non-leap) of each piece. Writes `logs/hierarchical/inputs/`.
"""

import numpy as np
import pandas as pd
from common import CORE, INPUTS, RELEASE, season_doy

from defile_passage import hourly as H
from defile_passage.export import in_window
from defile_passage.release import (
    MAIN_CATEGORY,
    TREKTELLEN_ERA,
    civil_twilight,
    outside_survey,
    parse_surveys,
)

YEARS = (1993, 2025)


def hour_pieces(frame: pd.DataFrame) -> pd.DataFrame:
    """`frame`'s intervals split at clock hours: `row` (its position), `slot_start`, `start`,
    `end`."""
    rows = []
    for i, start, end in zip(range(len(frame)), frame.start, frame.end):
        edges = [start, *pd.date_range(start.ceil("h"), end, freq="h", inclusive="left"), end]
        rows += [(i, a.floor("h"), a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]
    return pd.DataFrame(rows, columns=["row", "slot_start", "start", "end"])


def main():
    surveys = parse_surveys(pd.read_csv(RELEASE / "survey.csv", low_memory=False))
    surveys = surveys[
        surveys.survey_complete.eq(True)
        & surveys.date.dt.year.between(*YEARS)
        & in_window(surveys.date)
    ].reset_index(drop=True)
    surveys["weather_stop"] = surveys.weather_stop.eq(True)
    taxa = pd.read_csv(RELEASE / "taxonomy.csv")
    taxa = taxa[taxa.english_name.isin(CORE)]
    assert set(taxa.english_name) == set(CORE), "core species missing from the taxonomy"
    counts = pd.read_csv(RELEASE / "count.csv", low_memory=False)
    counts = counts[counts.count_category.eq(MAIN_CATEGORY) & counts.taxon_id.isin(taxa.taxon_id)]
    timing = H.count_timing(counts, surveys).merge(
        surveys[["survey_id", "date", "recording_era"]], on="survey_id"
    )
    # Unknown species-dates: an entry outside its survey, or presence without a number.
    raw = timing.datetime.fillna("")
    bounds = raw.where(raw.str.contains("/")).str.split("/", expand=True).reindex(columns=[0, 1])
    unknown = timing[
        timing.timing_status.isin(["outside_survey", "presence_only"])
        | outside_survey(timing)
        | pd.to_datetime(bounds[0], utc=True, format="ISO8601").lt(timing.start)
        | pd.to_datetime(bounds[1], utc=True, format="ISO8601").gt(timing.end)
    ][["taxon_id", "date"]].drop_duplicates()
    # A survey-species is split into hours only in Trektellen and when all its birds are timed.
    whole = timing[timing.slot_start.isna() & timing["count"].gt(0)]
    whole = set(zip(whole.survey_id, whole.taxon_id))
    hours = hour_pieces(surveys)
    hours = hours.assign(survey_id=surveys.survey_id.to_numpy()[hours.row]).drop(columns="row")
    trek = surveys.survey_id[surveys.recording_era.eq(TREKTELLEN_ERA)]
    INPUTS.mkdir(parents=True, exist_ok=True)
    for taxon in taxa.itertuples():
        mine = timing[timing.taxon_id.eq(taxon.taxon_id)]
        split = trek[[(s, taxon.taxon_id) not in whole for s in trek]]
        by_hour = mine[mine.survey_id.isin(split)].groupby(["survey_id", "slot_start"])["count"]
        hourly = hours[hours.survey_id.isin(split)].merge(
            by_hour.sum().rename("count").reset_index(), how="left"
        )
        kept = surveys[~surveys.survey_id.isin(split)]
        total = mine.groupby("survey_id")["count"].sum().rename("count")
        obs = pd.concat(
            [
                kept[["survey_id", "start", "end"]].join(total, on="survey_id"),
                hourly[["survey_id", "start", "end", "count"]],
            ],
            ignore_index=True,
        ).fillna({"count": 0.0})
        obs = obs.merge(surveys[["survey_id", "date", "weather_stop"]], on="survey_id")
        gone = unknown[unknown.taxon_id.eq(taxon.taxon_id)].date
        obs = obs[~obs.date.isin(gone)].sort_values("start").reset_index(drop=True)
        assert obs.loc[obs.weather_stop, "count"].eq(0).all(), "birds counted in a weather stop"
        obs["observation_id"] = np.arange(len(obs))
        obs["year"] = obs.date.dt.year
        obs["exposure_hours"] = (obs.end - obs.start) / pd.Timedelta(hours=1)

        parts = hour_pieces(obs)
        parts["observation_id"] = obs.observation_id.to_numpy()[parts.row]
        dates = obs.date.iloc[parts.row].reset_index(drop=True)
        dawn, dusk = civil_twilight(dates)
        midpoint = parts.start + (parts.end - parts.start) / 2
        parts["fraction"] = (parts.end - parts.start) / pd.Timedelta(hours=1)
        parts["tau"] = (midpoint - dawn) / (dusk - dawn)
        parts["doy"] = season_doy(dates).to_numpy()
        assert np.allclose(
            parts.groupby("observation_id").fraction.sum().to_numpy(), obs.exposure_hours
        )

        stem = INPUTS / taxon.english_name.replace(" ", "_")
        obs[
            [
                "observation_id",
                "survey_id",
                "date",
                "start",
                "end",
                "exposure_hours",
                "count",
                "year",
                "weather_stop",
            ]
        ].to_csv(f"{stem}_observations.csv", index=False)
        parts[["observation_id", "slot_start", "start", "end", "fraction", "tau", "doy"]].to_csv(
            f"{stem}_components.csv", index=False
        )
        print(
            f"{taxon.english_name}: {len(obs)} observations ({obs.weather_stop.sum()} weather"
            f" stop), {obs['count'].sum():.0f} birds, {len(gone)} unknown species-dates",
            flush=True,
        )


if __name__ == "__main__":
    main()
