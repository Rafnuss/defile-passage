"""The passage tables: analysis-ready numbers from the trend model, as a tabular data package
(`output/zenodo/`, with `DATA_GUIDE.md` and `DATA_DICTIONARY.md` as in defile-dataset's Zenodo
upload), for the Zenodo record beside the counts and for the data paper.

Read from the species files of the export, so they hold the numbers the page draws; nothing is
refitted. Only the taxa with a trend. Taxa are named by `taxon_id` alone: the names, ranks and
families are in `taxonomy.csv` of the counts record (`release.DATASET_DOI`). Method versions are in
`datapackage.json`, not in the rows. Every estimate carries its reliability (`RELIABILITY`).

Tables (`TABLES`, with each column's description):

- `daily_passage.csv`: every day of the taxon's window, counted or not: the count, its coverage and
  the full-day passage with its 95% interval.
- `trend.csv`: per taxon, the typical season's passage and the change in passage over the whole
  period and the last `trend.CHANGE_RECENT` years.
- `phenology.csv`: per taxon, the 10, 50 and 90% passage dates and their shift per decade.
"""

import json
import os

import pandas as pd

from .export import dumps
from .release import DATASET_DOI
from .trend import CHANGE_RECENT

METHOD = "passage-tables@3"
PASSAGE_DIR = "zenodo"  # beside the export (output/), like defile-dataset's Zenodo upload
NAME = "defile-passage-estimates"
TITLE = "Modelled passage of migrating birds at Défilé de l'Écluse, France"
LICENSE = {"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}
PASSAGE_DOI = "10.5281/zenodo.24084746"  # this package's own Zenodo record
DATASET_URL = "https://doi.org/{doi}"
DATASET_GITHUB_URL = "https://github.com/Rafnuss/defile-dataset/releases/tag/{tag}"
QUANTILES = (10, 50, 90)  # the passage dates: 10, 50 and 90% of the season passed
DECADE = 10  # the phenology slopes (days per year) given per decade

# The website's classes (`reliability`) in words for a reader of the tables
RELIABILITY = {"show": "reliable", "caveat": "caveat", "hide": "unreliable"}
RELIABLE = "reliable or caveat (usable with care); unreliable values are not published"
UNRELIABLE = "unreliable"

# What is published: what the website shows. A value classed hide by `reliability` (an unreliable
# day, trend, set of dates, or shifts alone) is left out; that includes every change over the
# years of passerines and groups of taxa (`reliability.EFFORT_ORDERS`, `TREND_RANKS`).

TAXON = ("taxon_id", "string", "Avibase concept ID: join to taxonomy.csv of the counts record")
R = CHANGE_RECENT

# table -> what a row is, for the descriptor and the guide
DESCRIPTIONS = {
    "daily_passage": "One row per taxon and day of its seasonal window, counted or not: the birds"
    " counted, the share of the day's passage the counting covered, and the estimated full-day"
    " passage with its 95% interval.",
    "trend": "One row per taxon: the passage of a typical recent season and the change in"
    f" passage over the whole period and the last {R} years, from the smooth long-term trend.",
    "phenology": "One row per taxon: the dates by which 10, 50 and 90% of the season's birds have"
    " passed, and how each has shifted per decade.",
}

# table -> [(column, type, description)]
TABLES = {
    "daily_passage": [
        TAXON,
        ("date", "date", "local calendar date (Europe/Paris)"),
        ("count", "integer", "birds counted on the day (main direction); empty when not counted"),
        ("coverage", "number", "share (0-1) of the day's passage in the minutes counted"),
        ("passage", "number", "estimated full-day passage (birds): mean over the model's draws"),
        ("passage_lower_95", "number", "lower end of the 95% interval of passage"),
        ("passage_upper_95", "number", "upper end of the 95% interval of passage"),
        ("reliability", "string", f"of passage: {RELIABLE}"),
    ],
    "trend": [
        TAXON,
        ("first_year", "integer", "first season modelled"),
        ("last_year", "integer", "last season modelled"),
        ("passage_recent", "number", f"birds in a typical season: median over the last {R}"),
        ("change", "number", "change in passage from first_year to last_year (%)"),
        ("change_lower_95", "number", "lower end of the 95% interval of change"),
        ("change_upper_95", "number", "upper end of the 95% interval of change"),
        ("change_recent", "number", f"change in passage over the last {R} years (%)"),
        ("change_recent_lower_95", "number", "lower end of the 95% interval of change_recent"),
        ("change_recent_upper_95", "number", "upper end of the 95% interval of change_recent"),
        ("reliability", "string", f"of passage_recent and the changes: {RELIABLE}"),
    ],
    "phenology": [
        TAXON,
        ("first_year", "integer", "first season modelled"),
        ("last_year", "integer", "last season modelled"),
        *[
            (
                f"date_{q}",
                "string",
                f"date (MM-DD) by which {q}% of the season's birds have passed," " in last_year",
            )
            for q in QUANTILES
        ],
        ("dates_reliability", "string", f"of the dates: {RELIABLE}"),
        *[
            col
            for q in QUANTILES
            for col in (
                (
                    f"shift_{q}",
                    "number",
                    f"shift of date_{q} in days per decade, from first_year"
                    " to last_year (negative: earlier)",
                ),
                (f"shift_{q}_lower_95", "number", f"lower end of the 95% interval of shift_{q}"),
                (f"shift_{q}_upper_95", "number", f"upper end of the 95% interval of shift_{q}"),
            )
        ],
        ("shifts_reliability", "string", f"of the shifts: {RELIABLE}"),
    ],
}


def _reliability(cls: dict, element: str) -> str | None:
    return RELIABILITY.get(cls.get(element))


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
            "passage_lower_95": t["q2.5"].round(1),
            "passage_upper_95": t["q97.5"].round(1),
            "reliability": _reliability(cls, "trend.days.total"),
        }
    )


def _percent(x) -> float | None:
    return None if x is None else round(100 * x, 1)


def _trend(d: dict, cls: dict) -> dict:
    t = d["trend"]
    last = t["last_year"]
    spans = {c["from"]: c for c in t.get("change", [])}
    whole, recent = spans.get(t["first_year"], {}), spans.get(last - R, {})
    return {
        "taxon_id": d["taxon_id"],
        "first_year": t["first_year"],
        "last_year": last,
        "passage_recent": d["key_numbers"].get("typical_season", {}).get("median"),
        "change": _percent(whole.get("change")),
        "change_lower_95": _percent(whole.get("lo")),
        "change_upper_95": _percent(whole.get("hi")),
        "change_recent": _percent(recent.get("change")),
        "change_recent_lower_95": _percent(recent.get("lo")),
        "change_recent_upper_95": _percent(recent.get("hi")),
        "reliability": _reliability(cls, "key_numbers.trend"),
    }


def _mmdd(year: int, doy) -> str | None:
    if doy is None or pd.isna(doy):
        return None
    return (pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=round(doy) - 1)).strftime(
        "%m-%d"
    )


def _phenology(d: dict, cls: dict) -> dict:
    last = d["trend"]["last_year"]
    p = d["key_numbers"].get("passage", {})
    fits = (d["season"].get("phenology") or {}).get("quantiles", {})
    out = {"taxon_id": d["taxon_id"], "first_year": d["trend"]["first_year"], "last_year": last}
    out |= {f"date_{q}": _mmdd(last, p.get(f"q{q}")) for q in QUANTILES}
    out["dates_reliability"] = _reliability(cls, "key_numbers.passage")
    for q in QUANTILES:
        fit = fits.get(f"q{q}", {})
        for col, key in (("", "slope"), ("_lower_95", "slope_lo"), ("_upper_95", "slope_hi")):
            v = fit.get(key)
            out[f"shift_{q}{col}"] = None if v is None else round(DECADE * v, 1)
    out["shifts_reliability"] = _reliability(cls, "season.phenology")
    return out


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
        days = _days(d, cls)
        rows["daily_passage"].append(days[days["reliability"] != UNRELIABLE])
        trend = _trend(d, cls)
        if trend["reliability"] != UNRELIABLE:
            rows["trend"].append(trend)
        phen = _phenology(d, cls)
        if phen["shifts_reliability"] == UNRELIABLE:
            phen |= {k: None for k in phen if k.startswith("shift")}
        if phen["dates_reliability"] != UNRELIABLE:
            rows["phenology"].append(phen)
    columns = {name: [c for c, _, _ in cols] for name, cols in TABLES.items()}
    out = {"daily_passage": pd.concat(rows["daily_passage"], ignore_index=True)}
    out |= {
        name: pd.DataFrame(rows[name], columns=columns[name]) for name in ("trend", "phenology")
    }
    return {name: out[name][columns[name]] for name in TABLES}


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
                    "primaryKey": ["taxon_id"] + (["date"] if name == "daily_passage" else []),
                    "foreignKeys": [taxonomy],
                },
            }
            for name, columns in TABLES.items()
        ],
    }


def guide(manifest: dict, t: dict[str, pd.DataFrame]) -> str:
    """`DATA_GUIDE.md`: how to read the tables, as defile-dataset's guide does for the counts."""
    n = len(t["trend"])
    files = {
        "daily_passage": "a taxon on one day of its seasonal window, counted or not",
        "trend": "a taxon: its typical passage and how it changed",
        "phenology": "a taxon: its passage dates and how they shifted",
    }
    lines = [
        f"# {TITLE}",
        "",
        f"Estimated passage of {n} taxa at Défilé de l'Écluse (Ain, France), from the autumn"
        f" migration counts. This record (https://doi.org/{PASSAGE_DOI}) holds model estimates"
        " only; the counts themselves, and `taxonomy.csv` that names each `taxon_id`, are in the"
        f" counts record (https://doi.org/{DATASET_DOI}, {dataset_name(manifest)}).",
        "",
        "This guide explains how to read the tables. [DATA_DICTIONARY.md](DATA_DICTIONARY.md)"
        " defines every column; `datapackage.json` holds the same definitions in machine-readable"
        " form ([Frictionless Data](https://frictionlessdata.io/)).",
        "",
        "## Files",
        "",
        "| File | One row is | Rows |",
        "| --- | --- | --- |",
    ]
    for name, df in t.items():
        lines.append(f"| `{name}.csv` | {files[name]} | {len(df)} |")
    lines += [
        "",
        "Every table links to the counts record by `taxon_id` (→ `taxonomy.csv`).",
        "",
        "## Reading the estimates",
        "",
        "- **Passage** is the number of birds that passed the count station in the main"
        " direction: the birds counted, plus those that passed while no one was counting, filled"
        " in by a negative-binomial GAM fitted to each taxon's counts (1000 draws). It describes"
        " the passage visible from the station, not population size.",
        "- **Daily.** `count` is the birds actually counted, `coverage` the share of the day's"
        " passage that fell in the minutes counted; on a day with `coverage` 0, `count` is empty"
        " and `passage` is entirely modelled. Sum `passage` over days for any period you need.",
        "- **Trend.** `change` is the change in passage from `first_year` to `last_year`, and"
        f" `change_recent` over the last {R} years, both in percent, from the smooth long-term"
        " trend (year-to-year noise removed). `passage_recent` gives the size of a typical season.",
        "- **Phenology.** `date_10`, `date_50` and `date_90` are the dates by which 10, 50 and"
        " 90% of the season's birds have passed, in `last_year`; `shift_*` is how much each date"
        " moved per decade, in days (negative: earlier).",
        "- **Intervals.** Columns ending `_lower_95` and `_upper_95` give the 95% interval of the"
        " column they follow.",
        "- **Reliability.** Only estimates that pass the reliability tests are published: each is"
        " `reliable` or `caveat` (usable with care; shown with a warning on the website). A day,"
        " trend or set of dates that failed a test is left out, and so are its shifts when only"
        " they failed.",
        "- **Which taxa.** `daily_passage` covers every taxon with a trend model. `trend` and"
        ' `phenology` cover species only (no "sp." or slash groups, whose numbers depend on how'
        " many birds were identified) and no passerines: they are counted systematically only"
        " from 2008, with growing attention since, so their change over time follows the counting"
        " effort more than the birds.",
        "",
        "## Example: species that declined",
        "",
        "In Python (pandas):",
        "",
        "```python",
        "import pandas as pd",
        "",
        'trend = pd.read_csv("trend.csv")',
        'taxonomy = pd.read_csv("taxonomy.csv")  # from the counts record',
        'trend = trend.merge(taxonomy[["taxon_id", "english_name"]], on="taxon_id")',
        'declined = trend[(trend["reliability"] == "reliable") & (trend["change_upper_95"] < 0)]',
        'print(declined[["english_name", "change", "change_lower_95", "change_upper_95"]])',
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
        "Every column of the tables. An empty cell means no value (not a hidden zero). The same"
        " definitions are in `datapackage.json` (Frictionless Data format).",
        "",
    ]
    for name, columns in TABLES.items():
        key = "`taxon_id`" + (" and `date`" if name == "daily_passage" else "")
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
