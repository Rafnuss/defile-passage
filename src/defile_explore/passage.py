"""The passage tables: the trend model's results as a tabular data package (`data/passage/`), for
the Zenodo record that sits beside the counts and for the data paper.

Read from the species files of the export, so they hold the numbers the page draws; nothing is
refitted. Only the taxa with a trend. Every value resting on a claim of `reliability` carries
its class (`show`, `caveat` or `hide`): a `hide` value is one the page does not draw.

Tables (`TABLES`, with each column's description):

- `taxa.csv`: the taxa, their years and window, the methods, the three claims' classes.
- `daily_passage.csv`: every window day, counted or not: the count, its coverage and the
  full-day passage (mean and 80% interval of the gap-filling draws).
- `season_totals.csv`: each year's passage over the window, and the smooth trend through them.
- `passage_dates.csv`: each year's dates by which 10, 50 and 90% of the season's birds passed, and
  the linear trend in each.
"""

import json
import os

import pandas as pd

from .export import dumps

METHOD = "passage-tables@1"
PASSAGE_DIR = "passage"  # beside the export, under the data dir
NAME = "defile-passage-estimates"
TITLE = "Modelled daily passage of migrating birds at Défilé de l'Écluse, France"
LICENSE = {"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}
DATASET_URL = "https://github.com/Rafnuss/defile-dataset/releases/tag/{tag}"
CLASS = "show, caveat or hide (reliability): hide is not drawn on the website"
DOY = "day of year (1 = 1 January), decimal"

# table -> [(column, type, description)]
TABLES = {
    "taxa": [
        ("taxon_id", "string", "Avibase concept ID, as in the dataset's taxonomy.csv"),
        ("english_name", "string", "English name"),
        ("scientific_name", "string", "scientific name"),
        ("first_year", "integer", "first year modelled (counted in full from then)"),
        ("last_year", "integer", "last complete season modelled"),
        ("window_start", "string", "first day of the modelled window (MM-DD)"),
        ("window_end", "string", "last day of the modelled window (MM-DD)"),
        ("totals", "string", f"class of the season totals: {CLASS}"),
        ("trend", "string", f"class of the long-term trend: {CLASS}"),
        ("season", "string", f"class of the season's shape and dates: {CLASS}"),
        ("dates_source", "string", "passage dates from the gap-filled days (gam) or count / c"),
        ("trend_method", "string", "trend model, name@version"),
        ("season_method", "string", "season block, name@version"),
        ("reliability_method", "string", "reliability rule, name@version"),
    ],
    "daily_passage": [
        ("taxon_id", "string", "Avibase concept ID"),
        ("date", "date", "local calendar date (Europe/Paris)"),
        ("coverage", "number", "share of the day's expected passage in the minutes counted"),
        ("count", "integer", "birds counted (main direction); empty when not counted"),
        ("passage", "number", "full-day passage: mean of the gap-filling draws"),
        ("passage_q10", "number", "10% quantile of the draws"),
        ("passage_q90", "number", "90% quantile of the draws"),
        ("class", "string", f"class of the daily passage: {CLASS}"),
    ],
    "season_totals": [
        ("taxon_id", "string", "Avibase concept ID"),
        ("year", "integer", "season"),
        ("counted", "integer", "birds counted in the window"),
        ("counted_share", "number", "counted / total: the share of the passage counted"),
        ("total", "number", "season passage: mean of the draws"),
        ("total_q2_5", "number", "2.5% quantile"),
        ("total_q10", "number", "10% quantile"),
        ("total_q90", "number", "90% quantile"),
        ("total_q97_5", "number", "97.5% quantile"),
        ("total_class", "string", f"class of the season totals: {CLASS}"),
        ("smooth", "number", "long-term trend: smooth season passage"),
        ("smooth_q2_5", "number", "2.5% quantile"),
        ("smooth_q97_5", "number", "97.5% quantile"),
        ("smooth_class", "string", f"class of the trend: {CLASS}"),
    ],
    "passage_dates": [
        ("taxon_id", "string", "Avibase concept ID"),
        ("year", "integer", "season"),
        ("q10", "number", f"date by which 10% of the season passed, {DOY}"),
        ("q50", "number", "date by which 50% passed"),
        ("q90", "number", "date by which 90% passed"),
        ("q50_lo", "number", "q50: lower end of its 80% interval"),
        ("q50_hi", "number", "q50: upper end of its 80% interval"),
        ("days_counted", "number", "share of the window's days counted"),
        ("class", "string", f"class of the yearly dates: {CLASS}"),
        ("q10_fit", "number", "linear trend in q10 over the years"),
        ("q10_fit_lo", "number", "q10_fit: lower end of its 95% interval"),
        ("q10_fit_hi", "number", "q10_fit: upper end"),
        ("q50_fit", "number", "linear trend in q50"),
        ("q50_fit_lo", "number", "lower end"),
        ("q50_fit_hi", "number", "upper end"),
        ("q90_fit", "number", "linear trend in q90"),
        ("q90_fit_lo", "number", "lower end"),
        ("q90_fit_hi", "number", "upper end"),
        ("fit_class", "string", f"class of the trends in dates: {CLASS}"),
    ],
}


def _taxon(d: dict, names: dict) -> dict:
    t, r = d["trend"], d["reliability"]
    return {
        "taxon_id": d["taxon_id"],
        "english_name": names[d["taxon_id"]]["english_name"],
        "scientific_name": names[d["taxon_id"]]["scientific_name"],
        "first_year": t["first_year"],
        "last_year": t["last_year"],
        "window_start": t["window"][0],
        "window_end": t["window"][1],
        "totals": r["totals"]["class"],
        "trend": r["trend"]["class"],
        "season": r["season"]["class"],
        "dates_source": d["season"]["source"],
        "trend_method": t["method"],
        "season_method": d["season"]["method"],
        "reliability_method": r["method"],
    }


def _days(d: dict, cls: dict) -> pd.DataFrame:
    t = pd.DataFrame(d["trend"]["days"])
    counted = t["c"] > 0
    return pd.DataFrame(
        {
            "taxon_id": d["taxon_id"],
            "date": t["date"],
            "coverage": t["c"],
            "count": t["count"].where(counted).astype("Int64"),
            "passage": t["total"],
            "passage_q10": t["q10"],
            "passage_q90": t["q90"],
            "class": cls.get("trend.days.total"),
        }
    )


def _totals(d: dict, cls: dict) -> pd.DataFrame:
    a = pd.DataFrame(d["trend"]["annual"])
    return pd.DataFrame(
        {
            "taxon_id": d["taxon_id"],
            "year": a["year"],
            "counted": a["observed"],
            "counted_share": a["observed_share"],
            "total": a["total"],
            "total_q2_5": a["q2.5"],
            "total_q10": a["q10"],
            "total_q90": a["q90"],
            "total_q97_5": a["q97.5"],
            "total_class": cls.get("trend.annual.total"),
            "smooth": a["smooth"],
            "smooth_q2_5": a["smooth_q2.5"],
            "smooth_q97_5": a["smooth_q97.5"],
            "smooth_class": cls.get("trend.annual.smooth"),
        }
    )


def _dates(d: dict, cls: dict) -> pd.DataFrame:
    p = pd.DataFrame(d["season"]["passage"]).rename(columns={"counted": "days_counted"})
    p.insert(0, "taxon_id", d["taxon_id"])
    p["class"] = cls.get("season.passage")
    for q, fit in d["season"]["phenology"]["quantiles"].items():
        f = pd.DataFrame(fit)[["year", "date", "lo", "hi"]]
        f.columns = ["year", f"{q}_fit", f"{q}_fit_lo", f"{q}_fit_hi"]
        p = p.merge(f, on="year", how="left")
    p["fit_class"] = cls.get("season.phenology")
    return p


def tables(export_dir: str) -> dict[str, pd.DataFrame]:
    """The four tables, from the export in `export_dir`."""
    with open(os.path.join(export_dir, "taxa.json"), encoding="utf-8") as f:
        names = {t["taxon_id"]: t for t in json.load(f)}
    rows = {name: [] for name in TABLES}
    for taxon_id in sorted(names):
        with open(os.path.join(export_dir, "species", f"{taxon_id}.json"), encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("trend"):
            continue
        cls = d["reliability"]["elements"]
        rows["taxa"].append(pd.DataFrame([_taxon(d, names)]))
        rows["daily_passage"].append(_days(d, cls))
        rows["season_totals"].append(_totals(d, cls))
        rows["passage_dates"].append(_dates(d, cls))
    return {
        name: pd.concat(parts, ignore_index=True)[[c for c, _, _ in TABLES[name]]]
        for name, parts in rows.items()
    }


def datapackage(manifest: dict) -> dict:
    """The Frictionless descriptor: the tables, their columns, and what they were made from."""
    tag = manifest.get("dataset_release")
    return {
        "name": NAME,
        "title": TITLE,
        "licenses": [LICENSE],
        "method": METHOD,
        "built_at": manifest["built_at"],
        "git_sha": manifest["git_sha"],
        "sources": [
            {
                "title": f"Défilé de l'Écluse migration counts, release {tag}",
                "path": DATASET_URL.format(tag=tag) if tag else None,
            }
        ],
        "resources": [
            {
                "name": name,
                "path": f"{name}.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": c, "type": t, "description": desc} for c, t, desc in columns
                    ],
                    "primaryKey": ["taxon_id"]
                    + (["date"] if name == "daily_passage" else [])
                    + (["year"] if name in ("season_totals", "passage_dates") else []),
                },
            }
            for name, columns in TABLES.items()
        ],
    }


def readme(manifest: dict, t: dict[str, pd.DataFrame]) -> str:
    """A short guide to the package, with its provenance."""
    lines = [
        f"# {TITLE}",
        "",
        "Model estimates derived from the counts at Défilé de l'Écluse, built by defile-passage"
        f" (`{manifest['git_sha']}`) from dataset release `{manifest.get('dataset_release')}`.",
        f"{len(t['taxa'])} taxa with a trend model; the counts themselves are in the dataset"
        " release, not here.",
        "",
        "Every estimate is a model output: the counts with their coverage, with the passage on"
        " uncounted minutes and days filled in by a negative-binomial GAM (1000 draws). The"
        " estimates describe the passage visible from the count station, not population size."
        " A value classed `hide` failed a reliability test and is not drawn on the website; a"
        " `caveat` value is drawn with a warning. The method is described in the data paper's"
        " appendix and at https://raphaelnussbaumer.com/defile-passage/.",
        "",
        "| Table | Rows | Contents |",
        "| --- | --- | --- |",
    ]
    contents = {
        "taxa": "one row per taxon: years, window, methods, reliability classes",
        "daily_passage": "one row per taxon and window day: count, coverage, passage",
        "season_totals": "one row per taxon and season: totals and the smooth trend",
        "passage_dates": "one row per taxon and season: 10/50/90% passage dates, their trends",
    }
    for name, df in t.items():
        lines.append(f"| `{name}.csv` | {len(df)} | {contents[name]} |")
    lines += ["", "Column definitions are in `datapackage.json`.", ""]
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
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme(manifest, t))
    return {name: len(df) for name, df in t.items()}
