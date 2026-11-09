"""The passage tables: analysis-ready numbers from the trend model, as a tabular data package
(`data/output/zenodo/`, with `DATA_GUIDE.md` and `DATA_DICTIONARY.md` as in defile-dataset's Zenodo
upload), for the Zenodo record beside the counts and for the data paper.

Read from the species files of the export, so they hold the numbers the page draws; nothing is
refitted. Only the taxa with a trend. Taxa are named by `taxon_id` alone: the names, ranks and
families are in `taxonomy.csv` of the counts record (`release.DATASET_DOI`). Method versions are in
`datapackage.json`, not in the rows. Every estimate carries its reliability (`RELIABILITY`).

Tables (`TABLES`, with each column's description):

- `daily_passage.csv`: every day of the taxon's window, counted or not: the count, its coverage and
  the full-day passage with its 80% interval.
- `seasonal_passage.csv`: each season: the window, the birds counted, the season's passage and its
  smooth long-term trend with 95% intervals, and the dates by which 10, 50 and 90% passed.
"""

import json
import os

import pandas as pd

from .export import dumps
from .release import DATASET_DOI

METHOD = "passage-tables@2"
PASSAGE_DIR = "zenodo"  # beside the export (output/), like defile-dataset's Zenodo upload
NAME = "defile-passage-estimates"
TITLE = "Modelled daily and seasonal passage of migrating birds at Défilé de l'Écluse, France"
LICENSE = {"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}
PASSAGE_DOI = "10.5281/zenodo.24084746"  # this package's own Zenodo record
DATASET_URL = "https://doi.org/{doi}"
DATASET_GITHUB_URL = "https://github.com/Rafnuss/defile-dataset/releases/tag/{tag}"

# The website's classes (`reliability`) in words for a reader of the tables
RELIABILITY = {"show": "reliable", "caveat": "caveat", "hide": "unreliable"}
RELIABLE = (
    "reliable, caveat (usable with care) or unreliable (failed a reliability test, not shown on"
    " the website)"
)

TAXON = ("taxon_id", "string", "Avibase concept ID: join to taxonomy.csv of the counts record")

# table -> what a row is, for the descriptor and the README
DESCRIPTIONS = {
    "daily_passage": "One row per taxon and day of its seasonal window, counted or not: the birds"
    " counted, the share of the day's passage the counting covered, and the estimated full-day"
    " passage with its 80% interval.",
    "seasonal_passage": "One row per taxon and season: the window, the birds counted, the season's"
    " estimated passage and its smooth long-term trend (95% intervals), and the dates by which 10,"
    " 50 and 90% of the season's birds had passed.",
}

# table -> [(column, type, description)]
TABLES = {
    "daily_passage": [
        TAXON,
        ("date", "date", "local calendar date (Europe/Paris)"),
        ("count", "integer", "birds counted on the day (main direction); empty when not counted"),
        ("coverage", "number", "share (0-1) of the day's passage in the minutes counted"),
        ("passage", "number", "estimated full-day passage (birds): mean over the model's draws"),
        ("passage_lower_80", "number", "lower end of the 80% interval of passage (10% quantile)"),
        ("passage_upper_80", "number", "upper end of the 80% interval of passage (90% quantile)"),
        ("reliability", "string", f"reliability of the daily passage: {RELIABLE}"),
    ],
    "seasonal_passage": [
        TAXON,
        ("year", "integer", "season"),
        ("window_start", "date", "first day of the seasonal window, the same each year"),
        ("window_end", "date", "last day of the seasonal window"),
        ("count", "integer", "birds counted in the window"),
        ("passage", "number", "estimated passage over the window (birds): mean over the draws"),
        ("passage_lower_95", "number", "lower end of the 95% interval of passage"),
        ("passage_upper_95", "number", "upper end of the 95% interval of passage"),
        ("passage_reliability", "string", f"reliability of passage: {RELIABLE}"),
        ("trend", "number", "smooth long-term trend in passage (birds), through the seasons"),
        ("trend_lower_95", "number", "lower end of the 95% interval of trend"),
        ("trend_upper_95", "number", "upper end of the 95% interval of trend"),
        ("trend_reliability", "string", f"reliability of trend: {RELIABLE}"),
        ("date_10", "date", "date by which 10% of the season's passage had gone by"),
        ("date_50", "date", "date by which 50% had gone by (median passage date)"),
        ("date_90", "date", "date by which 90% had gone by"),
        ("date_50_lower_80", "date", "lower end of the 80% interval of date_50"),
        ("date_50_upper_80", "date", "upper end of the 80% interval of date_50"),
        ("dates_reliability", "string", f"reliability of the three dates: {RELIABLE}"),
    ],
}


def _reliability(cls: dict, element: str) -> str | None:
    return RELIABILITY.get(cls.get(element))


def _date(year: pd.Series, doy: pd.Series) -> pd.Series:
    """Decimal day of year (1 = 1 January) to the nearest calendar date, empty when missing."""
    day = pd.to_datetime(year.astype(str) + "-01-01") + pd.to_timedelta(doy.round() - 1, unit="D")
    return day.dt.strftime("%Y-%m-%d")


def _days(d: dict, cls: dict) -> pd.DataFrame:
    t = pd.DataFrame(d["trend"]["days"])
    counted = t["c"] > 0
    return pd.DataFrame(
        {
            "taxon_id": d["taxon_id"],
            "date": t["date"],
            "count": t["count"].where(counted).astype("Int64"),
            "coverage": t["c"],
            "passage": t["total"],
            "passage_lower_80": t["q10"],
            "passage_upper_80": t["q90"],
            "reliability": _reliability(cls, "trend.days.total"),
        }
    )


def _seasons(d: dict, cls: dict) -> pd.DataFrame:
    a = pd.DataFrame(d["trend"]["annual"])
    start, end = d["trend"]["window"]
    out = pd.DataFrame(
        {
            "taxon_id": d["taxon_id"],
            "year": a["year"],
            "window_start": a["year"].astype(str) + f"-{start}",
            "window_end": a["year"].astype(str) + f"-{end}",
            "count": a["observed"],
            "passage": a["total"],
            "passage_lower_95": a["q2.5"],
            "passage_upper_95": a["q97.5"],
            "passage_reliability": _reliability(cls, "trend.annual.total"),
            "trend": a["smooth"],
            "trend_lower_95": a["smooth_q2.5"],
            "trend_upper_95": a["smooth_q97.5"],
            "trend_reliability": _reliability(cls, "trend.annual.smooth"),
        }
    )
    p = pd.DataFrame(d["season"]["passage"]).reindex(
        columns=["year", "q10", "q50", "q90", "q50_lo", "q50_hi"]
    )
    dates = pd.DataFrame({"year": p["year"]})
    for col, q in [
        ("date_10", "q10"),
        ("date_50", "q50"),
        ("date_90", "q90"),
        ("date_50_lower_80", "q50_lo"),
        ("date_50_upper_80", "q50_hi"),
    ]:
        dates[col] = _date(p["year"], p[q])
    dates["dates_reliability"] = _reliability(cls, "season.passage")
    return out.merge(dates, on="year", how="left")


def tables(export_dir: str) -> dict[str, pd.DataFrame]:
    """The tables, from the export in `export_dir`."""
    with open(os.path.join(export_dir, "taxa.json"), encoding="utf-8") as f:
        ids = sorted(t["taxon_id"] for t in json.load(f))
    rows = {name: [] for name in TABLES}
    for taxon_id in ids:
        with open(os.path.join(export_dir, "species", f"{taxon_id}.json"), encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("trend"):
            continue
        cls = d["reliability"]["elements"]
        rows["daily_passage"].append(_days(d, cls))
        rows["seasonal_passage"].append(_seasons(d, cls))
    return {
        name: pd.concat(parts, ignore_index=True)[[c for c, _, _ in TABLES[name]]]
        for name, parts in rows.items()
    }


def dataset_name(manifest: dict) -> str:
    """The dataset the tables come from: its release, or the build of a preview."""
    tag = manifest.get("dataset_release")
    return tag or f"build {(manifest.get('dataset_git_sha') or '')[:7]} (preview, not a release)"


def datapackage(manifest: dict) -> dict:
    """The Frictionless descriptor: the tables, their columns, and what they were made from."""
    tag = manifest.get("dataset_release")
    taxonomy = {
        "fields": "taxon_id",
        "reference": {"resource": "taxonomy", "fields": "taxon_id"},
        "description": f"taxonomy.csv of the counts record, https://doi.org/{DATASET_DOI}",
    }
    return {
        "name": NAME,
        "id": DATASET_URL.format(doi=PASSAGE_DOI),
        "title": TITLE,
        "licenses": [LICENSE],
        "method": METHOD,
        "built_at": manifest["built_at"],
        "git_sha": manifest["git_sha"],
        "sources": [
            {
                "title": f"Défilé de l'Écluse migration counts, {dataset_name(manifest)}",
                "path": DATASET_URL.format(doi=DATASET_DOI),
                "release": DATASET_GITHUB_URL.format(tag=tag) if tag else None,
            }
        ],
        "resources": [
            {
                "name": name,
                "path": f"{name}.csv",
                "description": DESCRIPTIONS[name],
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": c, "type": t, "description": desc} for c, t, desc in columns
                    ],
                    "primaryKey": ["taxon_id", "date" if name == "daily_passage" else "year"],
                    "foreignKeys": [taxonomy],
                },
            }
            for name, columns in TABLES.items()
        ],
    }


def guide(manifest: dict, t: dict[str, pd.DataFrame]) -> str:
    """`DATA_GUIDE.md`: how to read the tables, as defile-dataset's guide does for the counts."""
    n = t["seasonal_passage"]["taxon_id"].nunique()
    files = {
        "daily_passage": "a taxon on one day of its seasonal window, counted or not",
        "seasonal_passage": "a taxon in one season (year)",
    }
    lines = [
        f"# {TITLE}",
        "",
        f"Estimated passage of {n} taxa at Défilé de l'Écluse (Ain, France), by day and by season,"
        " from the autumn migration counts. This record (https://doi.org/"
        f"{PASSAGE_DOI}) holds model estimates only; the counts themselves, and `taxonomy.csv`"
        f" that names each `taxon_id`, are in the counts record (https://doi.org/{DATASET_DOI},"
        f" {dataset_name(manifest)}).",
        "",
        "This guide explains how to read the two tables. [DATA_DICTIONARY.md](DATA_DICTIONARY.md)"
        " defines every column; `datapackage.json` holds the same definitions in machine-readable"
        " form ([Frictionless Data](https://frictionlessdata.io/)).",
        "",
        "## Files",
        "",
        "| File | One row is | Rows | Links |",
        "| --- | --- | --- | --- |",
    ]
    for name, df in t.items():
        link = "`taxon_id` → `taxonomy.csv` of the counts record"
        lines.append(f"| `{name}.csv` | {files[name]} | {len(df)} | {link} |")
    lines += [
        "",
        "## Reading the estimates",
        "",
        "- **Passage.** `passage` is the number of birds that passed the count station in the main"
        " direction: the birds counted, plus those that passed while no one was counting (minutes"
        " and days not counted), filled in by a negative-binomial GAM fitted to each taxon's"
        " counts. It is the mean of 1000 draws; `_lower_` and `_upper_` columns give the interval"
        " named in their suffix (80 or 95%). It describes the passage visible from the station,"
        " not population size.",
        "- **Count and coverage.** `count` is the birds actually counted, `coverage` the share of"
        " the day's passage that fell in the minutes counted. A day with `coverage` 0 was not"
        " counted: `count` is empty and `passage` is entirely modelled.",
        "- **Seasonal window.** Each taxon is modelled over a fixed window of the year"
        " (`window_start` to `window_end`), the same every year; seasonal values cover that window"
        " only.",
        "- **Trend.** `trend` is the smooth long-term change in the seasonal passage, through the"
        " years: use it for change over time, `passage` for a given year.",
        "- **Passage dates.** `date_10`, `date_50` and `date_90` are the dates by which 10, 50 and"
        " 90% of the season's passage had gone by. They are empty when the season could not be"
        " estimated.",
        "- **Reliability.** Each estimate has a reliability: `reliable`, `caveat` (usable with"
        " care) or `unreliable` (failed a reliability test; not shown on the website). Filter on it"
        " before analysis.",
        "- **Dates** are local calendar dates (Europe/Paris), YYYY-MM-DD.",
        "",
        "## Example: seasonal passage of one species",
        "",
        "In Python (pandas):",
        "",
        "```python",
        "import pandas as pd",
        "",
        'seasons = pd.read_csv("seasonal_passage.csv")',
        'taxonomy = pd.read_csv("taxonomy.csv")  # from the counts record',
        'seasons = seasons.merge(taxonomy[["taxon_id", "english_name"]], on="taxon_id")',
        'kite = seasons[(seasons["english_name"] == "Red Kite")',
        '               & (seasons["passage_reliability"] != "unreliable")]',
        'print(kite[["year", "passage", "passage_lower_95", "passage_upper_95", "trend"]])',
        "```",
        "",
        "## Method",
        "",
        "The model is described in the data paper's appendix and at"
        " https://raphaelnussbaumer.com/defile-passage/. Built by defile-passage"
        f" (`{manifest['git_sha']}`, {METHOD}) on {manifest['built_at']}.",
        "",
    ]
    return "\n".join(lines)


def dictionary(t: dict[str, pd.DataFrame]) -> str:
    """`DATA_DICTIONARY.md`: every column, from `TABLES`."""
    lines = [
        "# Column definitions",
        "",
        "Every column of the two tables. An empty cell means no value (not a hidden zero). The same"
        " definitions are in `datapackage.json` (Frictionless Data format).",
        "",
    ]
    for name, columns in TABLES.items():
        key = "`taxon_id` and " + ("`date`" if name == "daily_passage" else "`year`")
        lines += [
            f"## {name}.csv",
            "",
            DESCRIPTIONS[name],
            "",
            f"One row per {key}. Links: `taxon_id` → `taxonomy.csv` of the counts record"
            f" (https://doi.org/{DATASET_DOI}).",
            "",
            "| Column | Type | Always filled | Meaning |",
            "| --- | --- | --- | --- |",
        ]
        for c, typ, desc in columns:
            filled = "yes" if t[name][c].notna().all() else ""
            lines.append(f"| `{c}` | {typ} | {filled} | {desc[0].upper() + desc[1:]}. |")
        lines.append("")
    lines += [
        "Reliability values (`reliability`, `*_reliability`):",
        "",
        "| Value | Meaning |",
        "| --- | --- |",
        "| `reliable` | passed the reliability tests |",
        "| `caveat` | usable with care: a test was borderline; shown with a warning on the website |",
        "| `unreliable` | failed a reliability test; not shown on the website |",
        "",
    ]
    return "\n".join(lines)


def write(export_dir: str, out_dir: str) -> dict[str, int]:
    """Write the package for the export in `export_dir` into `out_dir` (replaced).

    Rows per table.
    """
    with open(os.path.join(export_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    t = tables(export_dir)
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))
    for name, df in t.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
    with open(os.path.join(out_dir, "datapackage.json"), "w", encoding="utf-8") as f:
        f.write(dumps(datapackage(manifest)))
    for file, text in (
        ("DATA_GUIDE.md", guide(manifest, t)),
        ("DATA_DICTIONARY.md", dictionary(t)),
    ):
        with open(os.path.join(out_dir, file), "w", encoding="utf-8") as f:
            f.write(text)
    return {name: len(df) for name, df in t.items()}
