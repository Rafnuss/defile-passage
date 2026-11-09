"""The dataset release reader (`release.fetch_dataset`) and the passage tables (`passage`)."""

import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

from defile_passage import passage as P
from defile_passage import release as R


def _dataset_build(folder, edit=False):
    """A defile-dataset output folder: `zenodo/` and the build's `audit/metadata.json`."""
    upload = folder / R.DATASET_UPLOAD_DIR
    upload.mkdir(parents=True)
    (upload / "count.csv").write_text("taxon_id,count\nx,1\n")
    digest = hashlib.sha256((upload / "count.csv").read_bytes()).hexdigest()
    hashes = {f"{R.DATASET_UPLOAD_DIR}/count.csv": digest, "README.md": "not in the release"}
    (folder / "audit").mkdir()
    (folder.joinpath(*R.DATASET_METADATA_PATH)).write_text(
        json.dumps({"git_sha": "abc", "table_sha256": hashes})
    )
    if edit:
        (upload / "count.csv").write_text("taxon_id,count\nx,2\n")
    return folder


def test_local_dataset_build_is_copied_without_a_tag(tmp_path):
    release = R.fetch_dataset(str(_dataset_build(tmp_path / "out")), str(tmp_path / "data"))
    assert release["tag"] is None and release["git_sha"] == "abc"
    assert R.dataset_release(str(tmp_path / "data")) == release
    copied = sorted(os.listdir(tmp_path / "data" / R.DATASET_DIR))
    assert copied == ["count.csv", R.METADATA_FILE, R.RELEASE_FILE]


def test_edited_dataset_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="Not the files"):
        R.fetch_dataset(str(_dataset_build(tmp_path / "out", edit=True)), str(tmp_path / "data"))


def test_neither_tag_nor_folder(tmp_path):
    with pytest.raises(SystemExit, match="neither"):
        R.fetch_dataset("2026", str(tmp_path))


def _species(taxon_id):
    years = [2020, 2021]
    fit = {
        "year": years,
        "date": [250.0, 251.0],
        "slope": 0.12,
        "slope_lo": -0.05,
        "slope_hi": 0.3,
    }
    return {
        "taxon_id": taxon_id,
        "key_numbers": {
            "passage": {"q10": 240.2, "q50": 250.0, "q90": 260.0},
            "typical_season": {"median": 8.0},
        },
        "trend": {
            "method": "trend-gam@3",
            "change": [{"from": 2020, "to": 2021, "change": -0.221, "lo": -0.5, "hi": 0.1}],
            "first_year": 2020,
            "last_year": 2021,
            "window": ["07-14", "12-01"],
            "days": {
                "date": ["2020-09-01", "2020-09-02"],
                "c": [0.5, 0.0],
                "count": [3, 0],
                "total": [6.0, 2.0],
                "q2.5": [3.0, 0.0],
                "q97.5": [9.0, 7.0],
            },
            "annual": [
                {
                    "year": y,
                    "observed": 3,
                    "observed_share": 0.4,
                    "total": 8,
                    "q2.5": 5,
                    "q10": 6,
                    "q90": 10,
                    "q97.5": 12,
                    "smooth": 8,
                    "smooth_q2.5": 6,
                    "smooth_q97.5": 11,
                }
                for y in years
            ],
        },
        "season": {
            "method": "season@4",
            "source": "gam",
            "passage": [
                {"year": y, "q10": 240, "q50": 250, "q90": 260, "q50_lo": 248, "q50_hi": 252}
                | {"counted": 0.6}
                for y in years
            ],
            "phenology": {"quantiles": {"q10": fit, "q50": fit, "q90": fit}},
        },
        "reliability": {
            "method": "reliability@4",
            "totals": {"class": "show"},
            "trend": {"class": "caveat"},
            "season": {"class": "show"},
            "elements": {
                "trend.days.total": "show",
                "key_numbers.trend": "caveat",
                "season.phenology": "hide",
                "key_numbers.passage": "show",
            },
        },
    }


def test_passage_tables(tmp_path):
    export = tmp_path / "explore"
    (export / "species").mkdir(parents=True)
    species = {"taxon_rank": "species", "order": "Accipitriformes"}
    taxa = [
        {"taxon_id": "a"} | species,
        {"taxon_id": "b"} | species,
        {"taxon_id": "p", "taxon_rank": "species", "order": "Passeriformes"},
        {"taxon_id": "s", "taxon_rank": "spuh", "order": "Accipitriformes"},
        {"taxon_id": "c"} | species,
    ]
    (export / "taxa.json").write_text(json.dumps(taxa))
    (export / "species" / "a.json").write_text(json.dumps(_species("a")))
    (export / "species" / "b.json").write_text(json.dumps({"taxon_id": "b", "trend": None}))
    for other in ("p", "s"):  # the tables follow the classes, not the taxon
        (export / "species" / f"{other}.json").write_text(json.dumps(_species(other)))
    counts = _species("c")  # its season from the counts: no dates in the model's tables
    counts["season"]["source"] = "counts"
    counts["reliability"]["elements"] |= {"trend.days.total": "hide", "key_numbers.trend": "hide"}
    (export / "species" / "c.json").write_text(json.dumps(counts))
    manifest = {"built_at": "now", "git_sha": "abc", "dataset_release": "v2026.1"}
    (export / "manifest.json").write_text(json.dumps(manifest))

    rows = P.write(str(export), str(tmp_path / "passage"))
    assert rows == {"daily_passage": 6, "trend": 3, "phenology": 3}
    days = pd.read_csv(tmp_path / "passage" / "daily_passage.csv").query("taxon_id == 'a'")
    assert days["count"].isna().tolist() == [False, True]  # not counted: no count
    assert days["reliability"].tolist() == ["reliable"] * 2
    trend = pd.read_csv(tmp_path / "passage" / "trend.csv").iloc[0]
    assert (trend["change"], trend["change_lower_95"], trend["reliability"]) == (
        -22.1,
        -50,
        "read_with_care",
    )
    assert pd.isna(trend["change_recent"])  # no span from 2011
    phen = pd.read_csv(tmp_path / "passage" / "phenology.csv").iloc[0]
    assert (phen["first_year"], phen["date_50"], phen["dates_reliability"]) == (
        2020,
        "09-07",
        "reliable",
    )
    assert pd.isna(phen["shift_50"]) and pd.isna(
        phen["shifts_reliability"]
    )  # not shown: not published
    for name, columns in P.TABLES.items():
        table = pd.read_csv(tmp_path / "passage" / f"{name}.csv")
        assert table.columns.tolist() == [c for c, _, _ in columns]
    package = json.loads((tmp_path / "passage" / "datapackage.json").read_text())
    assert package["built_at"] == "now" and "v2026.1" in package["sources"][0]["release"]


def test_preview_names_the_dataset_build():
    preview = {"built_at": "now", "git_sha": "abc", "dataset_release": None}
    preview["dataset_git_sha"] = "fbbba31bf104"
    assert P.dataset_name(preview) == "build fbbba31 (preview, not a release)"
    assert P.datapackage(preview)["sources"][0]["release"] is None


def test_smooth_change():
    from defile_passage import trend as T

    years = np.arange(2000, 2021)
    smooth = np.tile(np.linspace(100, 50, len(years)), (200, 1))
    smooth[:, 0] *= np.linspace(0.9, 1.1, 200)  # spread over the draws
    whole, recent = T.smooth_change(years, smooth)
    assert (whole["from"], whole["to"], recent["from"]) == (2000, 2020, 2020 - T.CHANGE_RECENT)
    assert whole["lo"] < whole["change"] == -0.5 < whole["hi"]
    assert recent["change"] == round(50 / 75 - 1, 3)
    assert T.smooth_change(years, np.zeros((5, len(years)))) == []  # nothing to change from
