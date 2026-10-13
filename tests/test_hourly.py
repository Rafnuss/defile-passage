"""Scientific accounting checks for the independent hourly weather pilot."""

import pandas as pd

from defile_explore import hourly as H


def test_gap_mask_never_crosses_an_effort_break_and_ignores_bird_counts():
    start = pd.to_datetime(
        [
            "2024-09-01T07:00Z",
            "2024-09-01T08:00Z",
            "2024-09-01T10:00Z",
            "2024-09-01T11:00Z",
            "2024-09-01T12:00Z",
            "2024-09-01T13:00Z",
        ]
    )
    frame = pd.DataFrame(
        {
            "english_name": "Kite",
            "date": "2024-09-01",
            "year": 2024,
            "doy": 244,
            "start": start,
            "end": start + pd.Timedelta(hours=1),
            "rain_mm": [0, 1, 5, 2, 0, 0],
            "count": [0, 20, 0, 0, 8, 0],
        }
    )
    masks = H.validation_masks(frame)
    assert masks["hidden_hours"].tolist() == [False, False, True, True, False, False]
    pd.testing.assert_frame_equal(
        masks[["block_fold", "hidden_hours"]],
        H.validation_masks(frame.assign(count=999))[["block_fold", "hidden_hours"]],
    )
    assert masks["block_fold"].nunique() == 1


def test_split_preserves_empty_partial_hours_and_excludes_unobserved_statuses():
    surveys = pd.DataFrame(
        {
            "survey_id": ["observed", "rain", "incomplete"],
            "recording_era": ["trektellen"] * 3,
            "start": pd.to_datetime(["2023-09-01T09:20Z"] * 3),
            "end": pd.to_datetime(["2023-09-01T11:10Z"] * 3),
            "survey_complete": [True, True, False],
            "weather_stop": [None, True, None],
        }
    )
    hours = H.survey_hours(surveys)
    assert hours["survey_id"].tolist() == ["observed"] * 3
    assert hours["exposure_hours"].tolist() == [40 / 60, 1, 10 / 60]
    assert hours["exposure_hours"].sum() == 110 / 60


def test_untimed_birds_never_make_false_species_zeros_and_all_birds_reconcile():
    surveys = pd.DataFrame(
        {
            "survey_id": ["observed"],
            "recording_era": ["trektellen"],
            "start": pd.to_datetime(["2023-09-01T09:20Z"]),
            "end": pd.to_datetime(["2023-09-01T11:10Z"]),
            "survey_complete": [True],
            "weather_stop": [None],
        }
    )
    counts = pd.DataFrame(
        {
            "count_id": ["a", "b", "c", "d", "e"],
            "survey_id": ["observed"] * 5,
            "taxon_id": ["kite", "kite", "buzzard", "buzzard", "buzzard"],
            "datetime": [
                "2023-09-01T09:30Z",
                "2023-09-01",
                "2023-09-01T10:00Z/2023-09-01T11:00Z",
                "2023-09-01T09:40Z/2023-09-01T10:10Z",
                "2023-09-01T11:10Z",
            ],
            "count": [7, 13, 5, 11, 2],
            "count_category": ["normal"] * 5,
        }
    )
    timing = H.count_timing(counts, surveys)
    assert timing["timing_status"].tolist() == [
        "point",
        "untimed",
        "single_hour_interval",
        "untimed",
        "outside_survey",
    ]
    assert timing.loc[timing["slot_start"].notna(), "count"].sum() == 12
    assert timing.loc[timing["slot_start"].isna(), "count"].sum() == 26
    taxa = pd.DataFrame(
        {"taxon_id": ["kite", "buzzard", "osprey"], "english_name": ["Kite", "Buzzard", "Osprey"]}
    )
    frame = H.species_hours(H.survey_hours(surveys), timing, taxa)
    assert frame.loc[frame["taxon_id"].isin(["kite", "buzzard"]), "count"].isna().all()
    assert frame.loc[frame["taxon_id"].eq("osprey"), "count"].eq(0).all()
    assert frame["timed_count"].sum() == 12


def test_inherited_short_interval_is_supported_and_presence_is_not_a_zero():
    surveys = pd.DataFrame(
        {
            "survey_id": ["short"],
            "recording_era": ["trektellen"],
            "start": pd.to_datetime(["2023-09-01T09:20Z"]),
            "end": pd.to_datetime(["2023-09-01T09:50Z"]),
            "survey_complete": [True],
            "weather_stop": [None],
        }
    )
    counts = pd.DataFrame(
        {
            "count_id": ["a", "b"],
            "survey_id": ["short"] * 2,
            "taxon_id": ["kite", "osprey"],
            "datetime": [None, None],
            "count": [4, None],
            "count_category": ["normal"] * 2,
        }
    )
    timing = H.count_timing(counts, surveys)
    assert timing["timing_status"].tolist() == ["single_hour_interval", "presence_only"]
    taxa = pd.DataFrame({"taxon_id": ["kite", "osprey"], "english_name": ["Kite", "Osprey"]})
    frame = H.species_hours(H.survey_hours(surveys), timing, taxa)
    assert frame.loc[frame["taxon_id"].eq("kite"), "count"].iloc[0] == 4
    assert frame.loc[frame["taxon_id"].eq("osprey"), "count"].isna().all()


def test_recording_scope_does_not_turn_unmonitored_species_into_zeros():
    frame = pd.DataFrame(
        {
            "english_name": ["raptor", "passerine", "raptor"],
            "date": ["2023-09-01", "2023-09-01", "2010-09-01"],
            "count": [0.0, 5.0, 0.0],
            "timed_count": [0.0, 5.0, 0.0],
        }
    )
    scope = pd.DataFrame(
        {
            "english_name": ["raptor", "passerine"],
            "recording_scope": ["priority_target", "unverified"],
            "scope_from": [2022, 2022],
            "scope_to": [2025, 2025],
        }
    )
    result = H.recording_scope(frame, scope)
    assert result["scope_available"].tolist() == [True, False, False]
    assert result["count"].iloc[0] == 0
    assert result["count"].iloc[1:].isna().all()
    assert result["timed_count"].sum() == 5


def test_confirmed_recent_scope_does_not_create_historical_passerine_zeros():
    frame = pd.DataFrame(
        {
            "english_name": ["passerine", "passerine"],
            "date": ["2023-09-01", "2010-09-01"],
            "count": [0.0, 0.0],
            "timed_count": [0.0, 0.0],
        }
    )
    scope = pd.DataFrame(
        {
            "english_name": ["passerine"],
            "recording_scope": ["user_confirmed"],
            "scope_from": [2022],
            "scope_to": [2025],
        }
    )
    result = H.recording_scope(frame, scope)
    assert result["scope_available"].tolist() == [True, False]
    assert result["count"].iloc[0] == 0
    assert pd.isna(result["count"].iloc[1])
