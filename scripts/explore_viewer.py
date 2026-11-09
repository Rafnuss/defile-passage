#!/usr/bin/env python3
"""Build the QA decision table (`qa/`) from the production export.

Species-specific figures live in the methods guide; historical species pages redirect there. The
species comparison is its own page (`compare/`, `species_compare.py`).
"""

import argparse
import html
import json
import os
import re

import plotly

from defile_passage.export import EXPORT_DIR
from defile_passage.pipeline import KEY_YEARS
from defile_passage.reliability import CLASSES, FILL_ERROR, INTERVAL_RATIO, MIN_TRIALS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = "\n".join(
    open(os.path.join(ROOT, path), encoding="utf-8").read()
    for path in ("website/src/theme.css", "website/src/site-header.css", "website/public/qa.css")
)
HEADER = open(os.path.join(ROOT, "website/src/site-header.html"), encoding="utf-8").read()
CLAIMS = ("totals", "trend", "season")


def badge(level, text=None):
    return f'<span class="badge {level}">{html.escape(text or level)}</span>'


def taxon_details(tx, sp):
    name = html.escape(tx["english_name"])
    taxon = tx["taxon_id"]
    q = sp.get("reliability")
    reasons = ""
    if q:
        reasons = "".join(
            f"<tr><th>{claim}</th><td>{badge(q[claim]['class'])}</td><td>"
            + (
                ", ".join(html.escape(r["code"].replace("_", " ")) for r in q[claim]["reasons"])
                or "Checks passed"
            )
            + "</td></tr>"
            for claim in CLAIMS
        )
        elements = "".join(
            f"<tr><td>{html.escape(field)}</td><td>{badge(rule)}</td></tr>"
            for field, rule in q["elements"].items()
        )
        inputs = html.escape(json.dumps(q["inputs"], indent=2))
        reasons = f"<table><tr><th>Claim</th><th>Display</th><th>Reason</th></tr>{reasons}</table><details><summary>Rules by output and numerical inputs</summary><table>{elements}</table><pre>{inputs}</pre></details>"
    else:
        reasons = "<p>No fitted count model; descriptive counts only.</p>"
    edges = sp.get("window", {}).get("edges")
    if edges and edges.get("early"):
        cells = "".join(
            f"<tr><th>{end}</th><td>{edges[end]['index']}</td><td>{edges[end]['q10']}</td>"
            f"<td>{html.escape((edges[end]['level'] or '').replace('_', ' '))}</td></tr>"
            for end in ("early", "late")
        )
        reasons += (
            "<p>Passage where regular counting starts and stops: birds per full day in its first "
            "and last week against the season's average day, and the bootstrap q10 over years.</p>"
            f"<table><tr><th>Edge</th><th>Index</th><th>q10</th><th>Level</th></tr>{cells}</table>"
        )
    return (
        f"<details class='taxon-detail'><summary>{name}</summary><div class='decision-detail'>{reasons}"
        f"<p><a href='../index.html?species={taxon}#reliability'>Validation figures and methods →</a><br>"
        f"<a href='https://raphaelnussbaumer.com/defile/#explore/{taxon}'>Explore this species →</a></p></div></details>"
    )


def wrap(title, body, manifest=None, current="qa"):
    header = HEADER.replace("__ROOT__", "../").replace(
        f'data-page="{current}"', f'data-page="{current}" aria-current="page"'
    )
    js = plotly.offline.get_plotlyjs_version()
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Explore · Défilé de l’Écluse</title>
<link rel="icon" href="../favicon.png"><style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@{js}/plotly.min.js"></script>
</head><body><a class="skip-link" href="#main">Skip to content</a>{header}
<main id="main">{body}</main></body></html>"""


def gap_error(sp):
    return ((sp.get("benchmark") or {}).get("gap") or {}).get("abs_log_err")


INDEX_COLUMNS = (  # header, definition: the index's tooltips and its legend
    ("taxon", "English name; expand for display decisions and validation inputs."),
    (
        "group",
        "The species picker's group in defile-website (`taxa.json` `group`, by order). ★: in "
        "the default highlight list (`content/highlights.tsv`).",
    ),
    (
        "story",
        "How much of the defile-website page rests on the trend model: full (trend totals "
        "shown), caveat (shown with a caveat), counts (no trend, or its totals hidden: counts only).",
    ),
    ("from", "Start year (`settings.start_year`): nothing before it is adjusted or modelled."),
    ("birds", "All birds of this taxon ever counted, summed over every counted day."),
    (
        "profile",
        "Time-of-day profile used for coverage: own (fitted on this taxon's hourly "
        "counts), a group's (borrowed from similar taxa) or uniform (no profile).",
    ),
    (
        "coverage",
        f"Mean coverage c over the counted days of the last {KEY_YEARS} seasons: the "
        "share of the day's expected passage that was counted (1 = the whole day).",
    ),
    (
        "q90/q10",
        "Median over years of the gap-filled season total's q90 / q10: how wide the "
        f"trend's 80% intervals are. Above {INTERVAL_RATIO:g}: flag wide_intervals. Blank: no trend.",
    ),
    (
        "timed days",
        "Counted days with birds whose counts are timed to the hour: the sample of "
        "the time-of-day panel. 0: flag no_timed_days.",
    ),
    ("age yrs", "Number of years with enough birds aged to show the age block."),
    (
        "change",
        "Change of the smooth season total from the first to the last year of the trend "
        "(key_numbers.trend). Blank: no trend.",
    ),
    (
        "totals",
        "Reliability class of the gap-filled season totals (show / caveat / hide), from the "
        "gap benchmark, the share of each year filled and the interval widths. Sorts by severity.",
    ),
    (
        "trend",
        "Reliability class of the long-term trend (the smooth total): needs the totals, "
        "and a 95% band that is not too wide.",
    ),
    (
        "season",
        "Reliability class of the passage dates: width of their 80% bands, birds behind "
        "them, passage beyond regular counting.",
    ),
    (
        "gap error",
        "Gap benchmark: counted stretches are hidden and refilled by the trend model; "
        "median |log((estimate+1)/(counted+1))| over the trials. Caveat above "
        f"{FILL_ERROR[0]:g}, hide above {FILL_ERROR[1]:g} (with at least {MIN_TRIALS} trials). "
        "0.1 is about 10% off.",
    ),
    (
        "flags",
        "Diagnostics that may make the page misleading: borrowed_profile, "
        "passage_beyond_counting (birds still pass where regular counting starts or stops, "
        "in most years; _some_years: in a few), "
        "wide_intervals, no_timed_days. Sorts by number of flags.",
    ),
)
INDEX_JS = """
const t = document.getElementById('qa'), body = t.tBodies[0], qf = document.getElementById('qf');
const key = (td) => {
  const v = td.dataset.v !== undefined ? td.dataset.v : td.textContent.trim();
  return v === '' ? null : (isNaN(v) ? v.toLowerCase() : +v);
};
t.tHead.querySelectorAll('th').forEach((th, i) => th.querySelector('button').addEventListener('click', () => {
  const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
  t.tHead.querySelectorAll('th').forEach((h) => { delete h.dataset.dir; h.setAttribute('aria-sort', 'none'); });
  th.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : 'descending');
  th.dataset.dir = dir;
  const s = dir === 'asc' ? 1 : -1;
  [...body.rows].sort((a, b) => {
    const x = key(a.cells[i]), y = key(b.cells[i]);
    if (x === null || y === null) return (x === null) - (y === null);  // blanks last
    return (x < y ? -1 : x > y ? 1 : 0) * s;
  }).forEach((r) => body.appendChild(r));
}));
const count = () => {
  const n = [...body.rows].filter((r) => !r.hidden).length;
  document.getElementById('qn').textContent = n + ' / ' + body.rows.length + ' rows';
};
const group = document.getElementById('group'), model = document.getElementById('model');
const claim = document.getElementById('claim'), status = document.getElementById('status');
const flagged = document.getElementById('flagged');
const groups = [...new Set([...body.rows].map(r => r.dataset.group))].sort();
for (const value of groups) group.add(new Option(value, value));
function filter() {
  const words = qf.value.toLowerCase().split(/\\s+/).filter(Boolean);
  for (const r of body.rows) {
    const reliability = r.cells[+claim.value].textContent.trim();
    r.hidden = !words.every(w => r.textContent.toLowerCase().includes(w))
      || (group.value && r.dataset.group !== group.value)
      || (model.value && r.dataset.model !== model.value)
      || (status.value && reliability !== status.value)
      || (flagged.value && (+(r.cells[15].dataset.v) > 0) !== (flagged.value === 'yes'));
  }
  count();
}
for (const el of [qf, group, model, claim, status, flagged]) el.addEventListener('input', filter);
document.getElementById('reset').addEventListener('click', () => {
  for (const el of [qf, group, model, status, flagged]) el.value = '';
  claim.value = '11';
  filter();
});
count();
const selected = document.getElementById(decodeURIComponent(location.hash.slice(1)));
if (selected) { selected.querySelector('details').open = true; selected.scrollIntoView(); }
"""


def index(taxa: list, species: dict, manifest: dict | None = None) -> str:
    rows = []
    for tx in taxa:
        sp = species.get(tx["taxon_id"])
        if sp is None:
            continue
        d, k = sp["diagnostics"], sp["key_numbers"]
        rows.append((len(d["flags"]), tx, d, k, sp))
    rows.sort(key=lambda r: (-(r[1]["tier"] == "full"), -r[0], r[1]["english_name"]))

    def claim(sp, c):
        if not sp.get("reliability"):
            return "<td data-v=''></td>"
        cls = sp["reliability"][c]["class"]
        return f"<td data-v='{CLASSES.index(cls)}'>{badge(cls)}</td>"

    def num(v, fmt):
        return (
            f"<td class='n' data-v='{'' if v is None else v}'>"
            + ("" if v is None else format(v, fmt))
            + "</td>"
        )

    cells = "".join(
        f"<tr id='{tx['taxon_id']}' data-group='{tx.get('group', '')}' data-model='{str(bool(sp['trend'])).lower()}'><td>{taxon_details(tx, sp)}</td>"
        f"<td>{tx.get('group', '')}{' ★' if tx.get('highlight') else ''}</td>"
        f"<td>{tx.get('story') or ''}</td>"
        + num(tx["start_year"], "d")
        + num(tx["birds"] or 0, ",.0f")
        + f"<td>{d['profile']}</td>"
        + num(d["coverage_recent"], ".2f")
        + num(d.get("interval_ratio"), ".2f")
        + num(d["timed_days"], "d")
        + num(d["age_years"], "d")
        + num(k["trend"]["change"] if "trend" in k else None, "+.0%")
        + "".join(claim(sp, c) for c in CLAIMS)
        + num(gap_error(sp), ".3f")
        + f"<td data-v='{len(d['flags'])}'>"
        f"{''.join(f'<span class=flag>{f}</span>' for f in d['flags'])}</td></tr>"
        for _, tx, d, k, sp in rows
    )
    head = (
        "<tr>"
        + "".join(
            f"<th title='{html.escape(doc.replace('`', ''), quote=True)}' aria-sort='none'>"
            f"<button type='button'>{html.escape(name)}</button></th>"
            for name, doc in INDEX_COLUMNS
        )
        + "</tr>"
    )
    code = lambda d: re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(d))  # noqa: E731
    legend = "".join(f"<dt>{html.escape(n)}</dt><dd>{code(d)}</dd>" for n, d in INDEX_COLUMNS)
    body = f"""<section><h1>Quality assurance</h1><p>{len(rows)} taxa · Display decisions and diagnostics.</p>
<p class='note'>One row per taxon. Expand its name for display decisions and links. Click a column header to sort (again to reverse);
hover it for what the column means, defined in full below the table. The filter keeps the rows
whose text contains every word typed (e.g. <code>raptors caveat</code>).</p>
<div class='qa-filters'>
<label>Search taxa or flags<input id='qf' type='search' placeholder='e.g. kite or borrowed_profile'></label>
<label>Group<select id='group'><option value=''>All groups</option></select></label>
<label>Model<select id='model'><option value=''>All taxa</option><option value='true'>Fitted model</option><option value='false'>No fitted model</option></select></label>
<label>Claim<select id='claim'><option value='11'>Totals</option><option value='12'>Trend</option><option value='13'>Season</option></select></label>
<label>Reliability<select id='status'><option value=''>All classes</option><option>show</option><option>caveat</option><option>hide</option></select></label>
<label>Diagnostic flags<select id='flagged'><option value=''>All taxa</option><option value='yes'>With flags</option><option value='no'>Without flags</option></select></label>
<button id='reset' type='button'>Reset filters</button>
</div><span id='qn' class='note' role='status' aria-live='polite'></span>
<div class='panel'><table id='qa'><thead>{head}</thead><tbody>{cells}</tbody></table></div>
<details class='panel'><summary>Column definitions</summary><dl class='cols'>{legend}</dl></details>
</section><script>{INDEX_JS}</script>"""
    return wrap("Quality assurance", body, manifest)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", default=os.path.join(ROOT, "data", EXPORT_DIR))
    ap.add_argument("--out", default=os.path.join(ROOT, "data/output/site/qa"))
    args = ap.parse_args(argv)
    manifest = json.load(open(os.path.join(args.export, "manifest.json")))
    taxa = json.load(open(os.path.join(args.export, "taxa.json")))
    species = {
        tx["taxon_id"]: json.load(
            open(os.path.join(args.export, "species", f"{tx['taxon_id']}.json"))
        )
        for tx in taxa
        if tx["tier"] == "full"
    }
    os.makedirs(args.out, exist_ok=True)
    for taxon in species:
        url = f"../index.html?species={taxon}#reliability"
        with open(os.path.join(args.out, f"{taxon}.html"), "w") as f:
            f.write(
                f'<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={url}"><title>Validation and methods</title><a href="{url}">Validation and methods →</a></html>'
            )
    with open(os.path.join(args.out, "index.html"), "w") as f:
        f.write(index(taxa, species, manifest))
    print(f"QA table and {len(species)} historical redirects -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
