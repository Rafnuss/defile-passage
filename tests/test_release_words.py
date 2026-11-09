"""A v16 release (words, survey intervals on untimed entries) reads back as the codes Explore
uses."""

import pandas as pd

from defile_passage.release import from_release_words

SURVEY = pd.DataFrame(
    {"survey_id": ["S1"], "datetime": ["2023-09-15T06:00:00Z/2023-09-15T07:00:00Z"]}
)


def test_words_and_inherited_intervals_read_back():
    count = pd.DataFrame(
        {
            "survey_id": ["S1", "S1", "S1"],
            "datetime": [
                "2023-09-15T06:00:00Z/2023-09-15T07:00:00Z",  # carries its survey's interval
                "2023-09-15T06:12:00Z",
                "2023-09-15",
            ],
            "direction": ["main", "reverse", "local"],
            "count_estimation": ["approximate", None, "presence"],
        }
    )
    c = from_release_words(count, SURVEY)
    assert c["count_category"].tolist() == ["normal", "reverse", "local"]
    assert c["count_estimation"].tolist()[0] == "~" and c["count_estimation"].tolist()[2] == "x"
    assert pd.isna(c["datetime"].iloc[0])
    assert c["datetime"].iloc[1:].tolist() == ["2023-09-15T06:12:00Z", "2023-09-15"]


def test_an_older_release_is_unchanged():
    count = pd.DataFrame({"survey_id": ["S1"], "datetime": [None], "count_category": ["normal"]})
    assert from_release_words(count, SURVEY) is count
