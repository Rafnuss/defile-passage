"""Reading the defile-dataset release tables.

A copy, not a shared module: taken from defile-migration-forecast `src/data/counts.py` (commit
13c5107, 2026-10-09) when Explore moved to its own repo. Only what Explore reads is kept; the
forecast's survey-period processing stays there. The two repos are deliberately independent: a
change to one copy is carried to the other by hand, as a decision (DECISIONS.md -> Repository).

The release is defile-dataset's `dataset.zip` on its GitHub release `vYYYY.N`: the Zenodo upload
(`count.csv`, `survey.csv`, `taxonomy.csv`, `datapackage.json` and its guides) and the build's
`metadata.json` (the sha256 of each file). `scripts/build_explore.py --dataset vYYYY.N` downloads
it into `data/count/dataset/` (`fetch_dataset`); `--dataset <defile-dataset output folder>` copies
a local build instead, to try one before it is released, and such an export cannot be published.
`release.json` beside the tables says which it was.
"""

import hashlib
import io
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd
from suncalc import get_position

# defile-dataset's releases (`defile_dataset.release` there).
DATASET_REPO = "Rafnuss/defile-dataset"
DATASET_ASSET = "dataset.zip"
DATASET_URL = "https://github.com/{repo}/releases/download/{tag}/{asset}"
DATASET_TAG = re.compile(r"^v\d{4}\.\d+$")
DATASET_UPLOAD_DIR = "zenodo"  # in a defile-dataset output folder, and in metadata.json's hashes
RELEASE_FILE = "release.json"  # beside the tables: the tag they came from, or the local folder

# The site's local time: the dataset's dates are local calendar dates.
TIMEZONE = "Europe/Paris"
# Défilé de l'Écluse (lat, lon), as `LOCATIONS["Defile"]` in the forecast's weather layer.
SITE = (46.117215, 5.914877)

DATASET_DIR = os.path.join("count", "dataset")  # under the data dir
METADATA_FILE = "metadata.json"  # at the root of the release zip
DATASET_METADATA_PATH = ("audit", METADATA_FILE)  # in a defile-dataset output folder

# The main migration direction (`count.csv` `count_category`, `direction` since v16, read back by
# `from_release_words`); `reverse` and `local` are other
# quantities.
MAIN_CATEGORY = "normal"
# Presence without a number (`count_estimation`); its `count` is empty.
PRESENCE_ONLY = "x"
# The dataset keeps an entry timed outside its survey at day level, like an untimed one; only its
# `remark_processing` tells the two apart.
OUTSIDE_SURVEY_REMARK = "Entry time outside the native survey"
# The recording era of the surveys entered on trektellen.org (`survey.csv` `recording_era`).
TREKTELLEN_ERA = "trektellen"
# A count with its own interval up to this long is timed at the interval's midpoint; a longer one is
# kept at day level, like an untimed entry.
MAX_COUNT_INTERVAL = pd.Timedelta(hours=1)
# Civil twilight: the sun's altitude (deg) at dawn and dusk.
NIGHT_SUN_ALTITUDE = -6.0


def local_date(t: pd.Series) -> pd.Series:
    """Local calendar date (a naive midnight timestamp) of UTC times."""
    return t.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()


# Since schema v16 the release writes words where it wrote source codes; Explore keeps the codes
# (the species files carry `count_estimation` codes in `qualifiers`). Released word -> code.
RELEASE_WORDS = {
    "count_category": {"main": "normal", "reverse": "reverse", "local": "local"},
    "count_estimation": {"approximate": "~", "minimum": ">", "presence": "x"},
}


def from_release_words(count: pd.DataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    """`count.csv` of a v16 release in the form Explore reads: `count_category` with the codes, and
    an empty `datetime` for an entry that only carries its survey's interval.

    An older release is returned as it is.
    """
    if "direction" not in count:
        return count
    c = count.rename(columns={"direction": "count_category"})
    for column, words in RELEASE_WORDS.items():
        c[column] = c[column].map(words, na_action="ignore")
    inherited = c["datetime"].eq(c["survey_id"].map(survey.set_index("survey_id")["datetime"]))
    c.loc[inherited, "datetime"] = np.nan
    return c


def parse_surveys(survey: pd.DataFrame) -> pd.DataFrame:
    """`survey.csv` plus `start`/`end` (UTC), local `date` and `source`.

    `source` is `trektellen` or `historical` (notebook, spreadsheet, Naturalist, and the curated
    non-counting periods).
    """
    s = survey.copy()
    bounds = s["datetime"].str.split("/", expand=True)
    s["start"] = pd.to_datetime(bounds[0], utc=True)
    s["end"] = pd.to_datetime(bounds[1], utc=True)
    s["date"] = local_date(s["start"])
    s["source"] = np.where(s["recording_era"] == TREKTELLEN_ERA, "trektellen", "historical")
    return s


def outside_survey(counts: pd.DataFrame) -> pd.Series:
    """Entries the dataset marks as timed outside their survey."""
    return counts["remark_processing"].fillna("").str.startswith(OUTSIDE_SURVEY_REMARK)


def parse_counts(count: pd.DataFrame, surveys: pd.DataFrame, taxonomy: pd.DataFrame):
    """`count.csv` plus `species`, the `source` and `date` of its survey, and its own timestamp
    `datetime` (UTC; NaT when untimed).

    A count's `datetime` is either empty (it inherits its survey's interval), a local date (untimed,
    or timed outside its survey: the dataset keeps it at day level), a UTC time, or a UTC interval
    of its own (Trektellen's hourly entries since 2025): timed at its midpoint when it lasts up to
    `MAX_COUNT_INTERVAL`, kept at day level when longer.
    """
    c = count.copy()
    raw = c["datetime"].fillna("")
    own = raw.str.contains("/")
    raw[own] = raw[own].map(_interval_time)
    date_only = raw.str.len() == 10
    timed = raw.str.contains("T")
    c["datetime"] = pd.to_datetime(raw.where(timed), utc=True, format="ISO8601")
    c = c.merge(surveys[["survey_id", "source", "date"]], on="survey_id", how="left")
    assert c["source"].notna().all(), "count without a released survey"
    c.loc[timed.values, "date"] = local_date(c.loc[timed.values, "datetime"])
    c.loc[date_only.values, "date"] = pd.to_datetime(raw[date_only]).values
    c["count"] = c["count"].astype(float)  # presence-only counts are empty
    names = taxonomy.set_index("taxon_id")["english_name"]
    c["species"] = c["taxon_id"].map(names)
    return c


def _interval_time(interval: str) -> str:
    """A count's own interval as a UTC time (its midpoint) or, longer than `MAX_COUNT_INTERVAL`,
    the local date of its start."""
    start, end = (pd.Timestamp(t) for t in interval.split("/"))
    if end - start <= MAX_COUNT_INTERVAL:
        return (start + (end - start) / 2).isoformat()
    return str(local_date(pd.Series([start])).iloc[0].date())


def civil_twilight(dates: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Civil dawn and dusk at Defile on each local date, UTC: the first minute of the day with the
    sun at or above -6 deg, and the minute after the last (as defile-dataset computed them)."""
    lat, lon = SITE
    days = pd.DatetimeIndex(pd.to_datetime(dates.unique()))
    midnight = days.tz_localize(TIMEZONE).tz_convert("UTC")
    minutes = np.arange(24 * 60).astype("timedelta64[m]")
    grid = pd.DatetimeIndex((midnight.values[:, None] + minutes[None, :]).ravel())
    altitude = np.degrees(np.asarray(get_position(grid, lon, lat)["altitude"]))
    day = altitude.reshape(len(days), -1) >= NIGHT_SUN_ALTITUDE
    first = day.argmax(axis=1)
    last = day.shape[1] - 1 - day[:, ::-1].argmax(axis=1)
    dawn = dict(zip(days, midnight + pd.to_timedelta(first, unit="min")))
    dusk = dict(zip(days, midnight + pd.to_timedelta(last + 1, unit="min")))
    return dates.map(dawn), dates.map(dusk)


# --- Where the tables come from ---------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verified(files: dict[str, bytes]) -> dict[str, bytes]:
    """`files` (name -> bytes, `metadata.json` among them), after checking each table against the
    sha256 the dataset build gave it."""
    hashes = json.loads(files[METADATA_FILE])["table_sha256"]
    expected = {
        k.split("/", 1)[1]: v for k, v in hashes.items() if k.startswith(DATASET_UPLOAD_DIR + "/")
    }
    names = sorted(n for n in files if n != METADATA_FILE)
    if names != sorted(expected):
        raise SystemExit(f"The dataset holds {names}, its metadata.json lists {sorted(expected)}")
    changed = [n for n in names if _sha256(files[n]) != expected[n]]
    if changed:
        raise SystemExit(f"Not the files the dataset build wrote: {changed}")
    return files


def fetch_dataset(source: str, data_dir: str) -> dict:
    """Put a defile-dataset release in `<data_dir>/count/dataset/`, replacing what was there.

    `source` is a tag (`vYYYY.N`, downloaded from defile-dataset's GitHub release) or a defile-
    dataset output folder (its `zenodo/` and `audit/metadata.json`). Returns what `release.json`
    records: `tag` (None for a folder), `source` and `git_sha`.
    """
    if DATASET_TAG.match(source):
        url = DATASET_URL.format(repo=DATASET_REPO, tag=source, asset=DATASET_ASSET)
        try:
            with urllib.request.urlopen(url) as r, zipfile.ZipFile(io.BytesIO(r.read())) as z:
                files = {n: z.read(n) for n in z.namelist()}
        except urllib.error.HTTPError as e:
            raise SystemExit(f"No dataset release {source} ({e.code} for {url})") from e
        tag = source
    elif os.path.isdir(source):
        folder = os.path.join(source, DATASET_UPLOAD_DIR)
        files = {n: open(os.path.join(folder, n), "rb").read() for n in os.listdir(folder)}
        files[METADATA_FILE] = open(os.path.join(source, *DATASET_METADATA_PATH), "rb").read()
        tag, source = None, os.path.abspath(source)
    else:
        raise SystemExit(f"--dataset {source}: neither a tag vYYYY.N nor a folder")
    files = _verified(files)
    out = os.path.join(data_dir, DATASET_DIR)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for name, data in files.items():
        with open(os.path.join(out, name), "wb") as f:
            f.write(data)
    release = {
        "tag": tag,
        "source": source,
        "git_sha": json.loads(files[METADATA_FILE]).get("git_sha"),
    }
    with open(os.path.join(out, RELEASE_FILE), "w", encoding="utf-8") as f:
        json.dump(release, f, indent=2)
    return release


def dataset_release(data_dir: str) -> dict:
    """What `fetch_dataset` put in `<data_dir>/count/dataset/` (`tag` None when unknown)."""
    path = os.path.join(data_dir, DATASET_DIR, RELEASE_FILE)
    if not os.path.exists(path):
        return {"tag": None, "source": None, "git_sha": None}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
