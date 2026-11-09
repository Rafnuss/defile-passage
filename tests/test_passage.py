"""The dataset release reader (`release.fetch_dataset`) and the passage tables (`passage`)."""

import hashlib
import json
import os

import pandas as pd
import pytest

from defile_passage import passage as P
from defile_passage import release as R


def _dataset_build(folder, edit=False):
    """A defile-dataset output folder: `zenodo/` and the build's `metadata.json`."""
    upload = folder / R.DATASET_UPLOAD_DIR
    upload.mkdir(parents=True)
    (upload / "count.csv").write_text("taxon_id,count\nx,1\n")
    digest = hashlib.sha256((upload / "count.csv").read_bytes()).hexdigest()
    hashes = {f"{R.DATASET_UPLOAD_DIR}/count.csv": digest, "README.md": "not in the release"}
    (folder / R.METADATA_FILE).write_text(json.dumps({"git_sha": "abc", "table_sha256": hashes}))
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
    fit = {"year": years, "date": [250.0, 251.0], "lo": [248.0, 249.0], "hi": [252.0, 253.0]}
    return {
        "taxon_id": taxon_id,
        "trend": {
            "method": "trend-gam@3",
            "first_year": 2020,
            "last_year": 2021,
            "window": ["07-14", "12-01"],
            "days": {
                "date": ["2020-09-01", "2020-09-02"],
                "c": [0.5, 0.0],
                "count": [3, 0],
                "total": [6.0, 2.0],
                "q10": [4.0, 0.0],
                "q90": [8.0, 5.0],
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
            "elements": {"trend.days.total": "show", "trend.annual.smooth": "caveat"},
        },
    }


def test_passage_tables(tmp_path):
    export = tmp_path / "explore"
    (export / "species").mkdir(parents=True)
    taxa = [
        {"taxon_id": "a", "english_name": "A", "scientific_name": "Aa"},
        {"taxon_id": "b", "english_name": "B", "scientific_name": "Bb"},
    ]
    (export / "taxa.json").write_text(json.dumps(taxa))
    (export / "species" / "a.json").write_text(json.dumps(_species("a")))
    (export / "species" / "b.json").write_text(json.dumps({"taxon_id": "b", "trend": None}))
    manifest = {"built_at": "now", "git_sha": "abc", "dataset_release": "v2026.1"}
    (export / "manifest.json").write_text(json.dumps(manifest))

    rows = P.write(str(export), str(tmp_path / "passage"))
    assert rows == {"taxa": 1, "daily_passage": 2, "season_totals": 2, "passage_dates": 2}
    days = pd.read_csv(tmp_path / "passage" / "daily_passage.csv")
    assert days["count"].isna().tolist() == [False, True]  # not counted: no count
    for name, columns in P.TABLES.items():
        table = pd.read_csv(tmp_path / "passage" / f"{name}.csv")
        assert table.columns.tolist() == [c for c, _, _ in columns]
    package = json.loads((tmp_path / "passage" / "datapackage.json").read_text())
    assert package["built_at"] == "now" and "v2026.1" in package["sources"][0]["path"]
