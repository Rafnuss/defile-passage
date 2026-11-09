#!/usr/bin/env python3
"""Species comparison page of the Explore site (`compare/`): every taxon on one figure, one row
each, for the abundance trend, the passage dates, and the shift of the passage dates. It reads
`data/output/explore/` only; the figures are drawn in the browser (Plotly), so the filters (group,
species or grouping, tier, class on defile-website, name; edited in a panel and applied together),
the views and the sorts redraw them without a rebuild, and are kept in the page's URL so a view can
be shared.

One encoding for every figure: the colour is the taxon's group (`taxa.json` `group`); the symbol
is what defile-website does with the number drawn, from `reliability.elements` (filled: shown,
hollow: caveated, small grey: hidden, diamond: from the counts, no trend). Clicking a mark
highlights the taxon in all three figures and opens its card, with links to the methods guide,
the QA table and defile-website.

What each figure draws, and from which field:

- Abundance trend: `key_numbers.trend` (the change of the smooth total `trend.annual.smooth` from
  its first to its last year, the number defile-website shows), its class that of
  `key_numbers.trend`; or every year's smooth total against the taxon's own geometric mean (heat
  map). The export has no interval on the change itself: the one drawn combines the first and
  last years' 95% bands as if independent, so it is wider than the true interval (the level's
  uncertainty is shared by both years and cancels in the ratio).
- Passage: the 10/50/90% passage dates of `key_numbers.passage` (the smooth season of the last
  trend year, `trend.passage_q`, else the last `KEY_YEARS` counted seasons pooled), with the 80%
  band of that year's modelled median date (`trend.passage`); or the share of the season passing
  on each day, the last `KEY_YEARS` seasons of `season.share` pooled (heat map).
- Passage shift: linear changes in annual reconstructed dates (`season.phenology`), with 95%
  intervals carrying reconstruction uncertainty and between-year residual variation.

Usage:
    python scripts/species_compare.py          # -> data/output/site/compare/index.html
"""

import argparse
import json
import math
import os

import numpy as np
from explore_viewer import ROOT, wrap

from defile_passage.export import EXPORT_DIR
from defile_passage.pipeline import KEY_YEARS

Z95 = 1.959964  # normal quantile of the 95% two-sided band
TIERS = (  # tier on the page: its filter label; `excluded` taxa have no Explore page
    ("full", "full (trend, own page)"),
    ("short", "short"),
    ("rare", "rare"),
)
SPECIES_RANKS = ("species", "subspecies", "domestic")  # `taxon_rank`s of one kind of bird
RANKS = (  # filter value: label; `other` is a grouping (`spuh`, `slash`, `hybrid`)
    ("species", "species"),
    ("other", "sp., slash and hybrid"),
)
GROUPS = {  # catalogue group: colour (validated all-pairs, light)
    "raptors": "#c0562a",
    "passerines": "#3d6a8f",
    "waterbirds": "#3f8a8c",
    "other": "#7a4f7f",
}
CLASS_OF = {  # figure: the element of `reliability.ELEMENTS` its rows rest on
    "trend": "key_numbers.trend",
    "passage": "key_numbers.passage",
    "shift": "season.phenology",
}
GUIDE = {  # figure: the methods guide section that explains it
    "trend": "model-m-smooth",
    "passage": "shown-m-dates",
    "shift": "phenology-m-trend",
}
CLASS_LABELS = (  # class: label of its filter and of the symbol key
    ("show", "shown"),
    ("caveat", "caveated"),
    ("hide", "hidden"),
    ("counts", "from counts (no trend)"),
)
EXPLORE = "https://raphaelnussbaumer.com/defile/#explore/"


def num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def element_class(sp: dict, element: str) -> tuple[str, list[str]]:
    """The class defile-website gives `element`, and the reason codes of its claim; `counts` for a
    field from the counts alone (no trend)."""
    rel = sp.get("reliability")
    if not rel or element not in rel["elements"]:
        return "counts", []
    claim = {"key_numbers.trend": "trend"}.get(element, "season")
    return rel["elements"][element], [r["code"] for r in rel[claim]["reasons"]]


def trend_row(sp: dict) -> dict | None:
    t, kn = sp.get("trend"), sp["key_numbers"].get("trend")
    if not t or not kn or kn["change"] <= -1:
        return None
    a0, a1 = t["annual"][0], t["annual"][-1]
    if a0["smooth_q2.5"] and a1["smooth_q2.5"]:  # rounded to 0 for the rarest
        se = math.hypot(
            *(math.log(a["smooth_q97.5"] / a["smooth_q2.5"]) / (2 * Z95) for a in (a0, a1))
        )
    else:
        se = None
    log_ratio = math.log1p(kn["change"])
    smooth = [a["smooth"] for a in t["annual"]]
    gm = math.exp(np.mean(np.log(np.maximum(smooth, 1e-9))))
    cls, why = element_class(sp, CLASS_OF["trend"])
    return {
        "first": kn["from"],
        "last": kn["to"],
        "log": round(log_ratio, 4),
        "lo": None if se is None else round(log_ratio - Z95 * se, 4),
        "hi": None if se is None else round(log_ratio + Z95 * se, 4),
        "s0": a0["smooth"],
        "s1": a1["smooth"],
        "years": [a["year"] for a in t["annual"]],
        "rel": [round(math.log2(max(s, 1e-9) / gm), 3) for s in smooth],
        "cls": cls,
        "why": why,
    }


def passage_row(sp: dict) -> dict | None:
    p = sp["key_numbers"].get("passage")
    if not p or num(p["q50"]) is None:
        return None
    cls, why = (
        element_class(sp, CLASS_OF["passage"]) if p["source"] == "smooth" else ("counts", [])
    )
    out = {k: round(p[k], 1) for k in ("q10", "q50", "q90")} | {"source": p["source"]}
    if sp.get("trend"):
        last = sp["trend"]["passage"][-1]
        out |= {"year": last["year"], "q50_lo": last["lo"], "q50_hi": last["hi"]}
    s = sp["season"]
    years = np.asarray(s["years"])
    keep = years > years.max() - KEY_YEARS
    out |= {"from": int(years[keep].min()), "to": int(years[keep].max())}
    pooled = np.nan_to_num(np.asarray(s["share"], float)[keep]).sum(axis=0)
    if pooled.max() > 0:
        out |= {"doy": s["doy"], "density": np.round(pooled / pooled.max(), 3).tolist()}
    return out | {"cls": cls, "why": why}


def shift_row(sp: dict) -> dict | None:
    q = sp["season"].get("phenology", {}).get("quantiles", {})
    if not q:
        return None
    years = q["q50"]["year"]
    span = years[-1] - years[0]
    out = {"first": years[0], "last": years[-1]}
    for name, fit in q.items():
        out[name] = {
            "d": fit["slope"] * span,
            "lo": fit["slope_lo"] * span,
            "hi": fit["slope_hi"] * span,
            "from": fit["date"][0],
            "to": fit["date"][-1],
        }
    cls, why = element_class(sp, CLASS_OF["shift"])
    return out | {"cls": cls, "why": why}


def rows(taxa: list, export: str) -> list:
    out = []
    for tx in taxa:
        path = os.path.join(export, "species", f"{tx['taxon_id']}.json")
        if tx["tier"] not in dict(TIERS) or not os.path.exists(path):
            continue
        sp = json.load(open(path))
        row = {
            "id": tx["taxon_id"],
            "en": tx["english_name"],
            "fr": tx["french_name"],
            "sci": tx["scientific_name"],
            "group": tx.get("group") or "other",
            "tier": tx["tier"],
            "rank": "species" if tx.get("taxon_rank", "species") in SPECIES_RANKS else "other",
            "order": tx.get("taxon_order") or 0,
            "birds": tx.get("season_birds") or 0,
            "page": tx["tier"] == "full",  # the methods guide and QA table have its row
            "trend": trend_row(sp),
            "passage": passage_row(sp),
            "shift": shift_row(sp),
        }
        if row["trend"] or row["passage"]:
            out.append(row)
    return out


def glyph(cls: str, color: str = "#625c53", size: int = 12) -> str:
    """The symbol of a class as inline SVG, as the figures draw it (`markers` in JS)."""
    r, c = size / 2, size / 2
    if cls == "counts":
        shape = f'<path d="M{c} 1L{size - 1} {c}L{c} {size - 1}L1 {c}Z" fill="{color}"/>'
    elif cls == "hide":
        shape = f'<circle cx="{c}" cy="{c}" r="{r - 3}" fill="#bdb6a7" stroke="#948d82"/>'
    else:
        fill = color if cls == "show" else "#fff"
        shape = (
            f'<circle cx="{c}" cy="{c}" r="{r - 1.5}" fill="{fill}" stroke="{color}" '
            'stroke-width="1.6"/>'
        )
    return (
        f'<svg class="gl" width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'aria-hidden="true">{shape}</svg>'
    )


CSS = """
@media(max-width:1000px){.bar{top:0!important}}
@media(max-width:700px){.bar{position:static!important}}
.bar{position:sticky;top:var(--explore-header-height);z-index:8;background:var(--dv-paper);
 border-bottom:1px solid var(--dv-line);padding:8px 3vw;font-size:13px}
.bar-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.summary{color:var(--dv-muted);font-size:12px;flex:1;min-width:200px}
.summary b{color:var(--dv-ink);font-weight:600}
.bar button{font-size:13px;padding:4px 12px;border:1px solid var(--dv-line);border-radius:4px;
 background:var(--dv-surface);color:var(--dv-ink);cursor:pointer}
.bar button.primary{background:var(--dv-accent);border-color:var(--dv-accent);color:#fff}
.bar button.primary:disabled{opacity:.45;cursor:default}
.bar button.quiet{border-color:transparent;background:none;color:var(--dv-accent);text-decoration:underline;
 text-underline-offset:3px;padding:4px 6px}
#f-toggle::after{content:" ▾"}
#f-toggle[aria-expanded=true]::after{content:" ▴"}
#f-panel{margin-top:10px;padding:12px 14px;background:var(--dv-surface);border:1px solid var(--dv-line);
 border-radius:var(--dv-radius);max-height:70vh;overflow:auto}
#f-panel[hidden]{display:none}
.f-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px 24px}
.f-grid fieldset{border:0;margin:0;padding:0;display:flex;flex-direction:column;gap:5px;min-width:0}
.f-grid legend{font-weight:600;font-size:12px;color:var(--dv-muted);text-transform:uppercase;
 letter-spacing:.05em;margin-bottom:6px;padding:0;display:flex;gap:8px;align-items:baseline;width:100%}
.f-grid legend .qs{font-weight:400;text-transform:none;letter-spacing:0;margin-left:auto}
.f-grid legend .qs button{border:0;background:none;padding:0;color:var(--dv-accent);font-size:12px;cursor:pointer;text-decoration:underline}
.f-grid label{display:flex;align-items:center;gap:6px;cursor:pointer}
.f-grid fieldset.empty legend{color:var(--dv-red)}
.f-name input{padding:4px 8px;border:1px solid var(--dv-line);border-radius:4px;font-size:13px;width:100%;box-sizing:border-box}
.hint{font-size:11px;color:var(--dv-faint)}
.f-foot{display:flex;align-items:center;gap:10px;margin-top:12px;padding-top:10px;border-top:1px solid var(--dv-line)}
#f-preview{flex:1;font-size:12px;color:var(--dv-muted)}
#f-preview.warn{color:var(--dv-red)}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px}
.gl{flex:none;vertical-align:-1px}
.ctl{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font-size:13px;margin:4px 8px}
.ctl select{font-size:13px;padding:2px 4px}
.seg{display:inline-flex}
.seg[hidden]{display:none}
.seg button{border:1px solid var(--dv-line);background:var(--dv-surface);padding:3px 10px;
 font-size:12px;cursor:pointer;color:var(--dv-ink)}
.seg button:first-child{border-radius:4px 0 0 4px}
.seg button:last-child{border-radius:0 4px 4px 0}
.seg button+button{border-left:0}
.seg button[aria-pressed=true]{background:var(--dv-accent);color:#fff;border-color:var(--dv-accent)}
.count{color:var(--dv-muted);font-size:12px;margin-left:auto}
.key{font-size:12px;color:var(--dv-muted);margin:4px 8px;display:flex;flex-wrap:wrap;gap:4px 16px}
.key>span{white-space:nowrap;display:inline-flex;align-items:center;gap:5px}
.ln{display:inline-block;width:18px;height:0;border-top:2px solid}
.bx{display:inline-block;width:18px;height:6px;border-radius:1px}
.fig{min-height:120px}
h3[id]{scroll-margin-top:70px}
.empty{color:var(--dv-muted);font-size:13px;padding:24px 8px}
#card{position:fixed;right:16px;bottom:16px;z-index:20;width:min(380px,calc(100vw - 32px));
 background:var(--dv-surface);border:1px solid var(--dv-line);border-left:4px solid var(--dv-gold);
 border-radius:var(--dv-radius);box-shadow:0 6px 24px rgba(0,0,0,.12);padding:12px 14px;font-size:13px}
#card[hidden]{display:none}
#card h4{margin:0 22px 2px 0;font-size:15px}
#card .sub{color:var(--dv-muted);font-size:12px;margin-bottom:8px}
#card dl{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;margin:0 0 8px}
#card dt{color:var(--dv-muted)}
#card dd{margin:0}
#card .close{position:absolute;top:6px;right:8px;border:0;background:none;font-size:18px;
 cursor:pointer;color:var(--dv-muted)}
#card .links a{margin-right:10px;white-space:nowrap}
"""

BODY = """
<div class="bar" role="search" aria-label="Filter the taxa of all three figures">
 <div class="bar-row">
  <button id="f-toggle" type="button" class="primary" aria-expanded="false" aria-controls="f-panel">Filters</button>
  <span id="f-summary" class="summary"></span>
  <button id="reset" type="button" class="quiet">Reset to default</button>
 </div>
 <form id="f-panel" hidden>
  <div class="f-grid">
   <fieldset id="f-group"><legend>Group</legend>__GROUPS__</fieldset>
   <fieldset id="f-rank"><legend>Taxa</legend>__RANKS__</fieldset>
   <fieldset id="f-tier"><legend>Tier</legend>__TIERS__</fieldset>
   <fieldset id="f-cls"><legend>On defile-website</legend>__CLASSES__</fieldset>
   <fieldset class="f-name"><legend>Name</legend><input id="f-name" type="search"
    placeholder="English, French, Latin" aria-label="Filter by name"><span class="hint">Any part of a name; empty: all</span></fieldset>
  </div>
  <div class="f-foot">
   <span id="f-preview" role="status"></span>
   <button type="button" id="f-cancel" class="quiet">Cancel</button>
   <button type="submit" id="f-apply" class="primary">Apply</button>
  </div>
 </form>
</div>
<section>
<h1>Species comparison</h1>
<p class="note">One row per taxon, in three figures: abundance trend, passage dates, and the
shift of the passage dates. The filters (button above) apply to all three, once applied; by default, species of the full tier whose number defile-website shows. Colour is the taxon's group;
the symbol is what defile-website does with the number drawn (the figure's own claim, so a taxon
can be shown in one figure and hidden in another), as in the filter: __GLYPHS__. Hover a mark for
its numbers; click it to highlight the taxon in all three figures and open its links. The view is
kept in the address bar, ready to share.</p>

<h3 id="trend">1. Abundance trend</h3>
<div class="panel">
 <div class="ctl">
  <span class="seg" id="t-view" role="group" aria-label="View"><button data-v="dots">Change</button><button data-v="heat">Trajectory</button></span>
  <span class="seg" id="t-unit" role="group" aria-label="Unit"><button data-v="total">first to last year</button><button data-v="year">per year</button></span>
  <label>Sort <select id="t-sort">
   <option value="value">by change</option><option value="order">taxonomic</option>
   <option value="birds">by birds per season</option><option value="name">by name</option>
   <option value="group">by group, then change</option></select></label>
  <span class="count" id="t-count" role="status"></span>
 </div>
 <div class="key" id="t-key"></div>
 <div id="fig-trend" class="fig"></div>
 <p class="note">Change of the smooth total (the trend without each year's level and weather
 episodes), from the taxon's first trend year to __LAST__, as defile-website states it
 (<code>key_numbers.trend</code>). Taxa whose trend starts later than __FIRST__ are marked with
 their start year: compare them per year. Interval: 95%, conservative (the two years' bands
 combined as if independent; the export carries no interval on the change itself). Trajectory:
 each year's smooth total against the taxon's geometric mean over its years
 (<code>trend.annual.smooth</code>).</p>
</div>

<h3 id="passage">2. Passage dates</h3>
<div class="panel">
 <div class="ctl">
  <span class="seg" id="p-view" role="group" aria-label="View"><button data-v="range">10-50-90%</button><button data-v="heat">Season</button></span>
  <label>Sort <select id="p-sort">
   <option value="q50">by median date</option><option value="q10">by 10% date</option>
   <option value="q90">by 90% date</option><option value="span">by span (10-90%)</option>
   <option value="order">taxonomic</option><option value="birds">by birds per season</option>
   <option value="name">by name</option><option value="group">by group, then median</option></select></label>
  <span class="count" id="p-count" role="status"></span>
 </div>
 <div class="key" id="p-key"></div>
 <div id="fig-passage" class="fig"></div>
 <p class="note">The passage dates defile-website states (<code>key_numbers.passage</code>).
 With a trend: the smooth season of the last trend year (__LAST__); the whisker is the 80% band
 of that year's modelled median date (<code>trend.passage</code>). Without a trend: the last
 __KEY_YEARS__ counted seasons pooled, no band. Season: each day's share of the season, the last
 __KEY_YEARS__ seasons of <code>season.share</code> pooled, scaled to the taxon's peak day.</p>
</div>

<h3 id="shift">3. Shift of the passage dates</h3>
<div class="panel">
 <div class="ctl">
  <span class="seg" id="s-q" role="group" aria-label="Passage date"><button data-v="q10">10%</button><button data-v="q50">median</button><button data-v="q90">90%</button><button data-v="all">all three</button></span>
  <span class="seg" id="s-unit" role="group" aria-label="Unit"><button data-v="total">first to last year</button><button data-v="decade">per decade</button></span>
  <label>Sort <select id="s-sort">
   <option value="value">by shift</option><option value="q50">by median date</option>
   <option value="order">taxonomic</option><option value="birds">by birds per season</option>
   <option value="name">by name</option><option value="group">by group, then shift</option></select></label>
  <span class="count" id="s-count" role="status"></span>
 </div>
 <div class="key" id="s-key"></div>
 <div id="fig-shift" class="fig"></div>
 <p class="note">Change in the annual reconstructed 10%, 50% and 90% passage dates, from the
 linear fits of the methods guide (<code>season.phenology</code>). Intervals are 95%, combining
 the joint reconstruction uncertainty and residual resampling across years. defile-website draws
 these lines only when the season claim is shown (no caveat).</p>
</div>
</section>
<aside id="card" hidden aria-live="polite"></aside>
<script>
const DATA = __DATA__;
const GROUPS = __GROUP_COLORS__;
const GUIDE = __GUIDE__;
const EXPLORE = __EXPLORE__;
const DEFAULTS = __DEFAULTS__;
__JS__
</script>
"""

JS = r"""
const ROW = 16, TOP = 56, BOTTOM = 24, MIRROR_ROWS = 30;
const INK = "#24211d", MUTED = "#625c53", GRID = "#ece7dc", ZERO = "#948d82", PAPER = "#ffffff";
const HIDE_FILL = "#bdb6a7", HIDE_LINE = "#948d82", SELECT = "#fbf3dc", SELECT_LINE = "#d9a92e";
const CLS_NAME = {show: "shown", caveat: "caveated", hide: "hidden", counts: "from counts (no trend)"};
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DOY_TICKS = [182, 196, 213, 227, 244, 258, 274, 288, 305, 319, 335];
const YEARS = (() => { const y = DATA.flatMap((r) => r.trend ? r.trend.years : []); return [Math.min(...y), Math.max(...y)]; })();

// --- state, kept in the URL ---------------------------------------------------
const state = JSON.parse(JSON.stringify(DEFAULTS));
const SETS = ["group", "rank", "tier", "cls"];
function readUrl() {
  const u = new URLSearchParams(location.search);
  for (const k of SETS) if (u.has(k)) state[k] = u.get(k) ? u.get(k).split(",") : [];
  if (u.has("name")) state.name = u.get("name");
  if (u.has("sel")) state.sel = u.get("sel");
  for (const k of ["t", "p", "s"]) if (u.has(k)) {
    const parts = u.get(k).split("."), keys = Object.keys(DEFAULTS[k]);
    keys.forEach((key, i) => { if (parts[i]) state[k][key] = parts[i]; });
  }
}
function writeUrl() {
  const u = new URLSearchParams();
  for (const k of SETS) if (state[k].join() !== DEFAULTS[k].join()) u.set(k, state[k].join());
  if (state.name) u.set("name", state.name);
  for (const k of ["t", "p", "s"]) {
    const v = Object.keys(DEFAULTS[k]).map((key) => state[k][key]).join(".");
    if (v !== Object.values(DEFAULTS[k]).join(".")) u.set(k, v);
  }
  if (state.sel) u.set("sel", state.sel);
  const q = u.toString();
  history.replaceState(null, "", location.pathname + (q ? "?" + q.replace(/%2C/g, ",") : "") + location.hash);
}

// --- formatting ---------------------------------------------------------------
function date(doy) {  // day of year (non-leap) -> "12 Sep"
  const d = new Date(Date.UTC(2025, 0, 1) + (Math.round(doy) - 1) * 864e5);
  return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()];
}
const pct = (lr) => { const v = Math.exp(lr) - 1; if (Math.abs(v) < 5e-4) return "0%"; return (v >= 0 ? "+" : "−") + (Math.abs(v) < 0.1 ? (100 * Math.abs(v)).toFixed(1) : Math.round(100 * Math.abs(v))) + "%"; };
const signed = (v, d = 0) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const why = (c) => CLS_NAME[c.cls] + (c.why.length ? ` (${c.why.join(", ").replace(/_/g, " ")})` : "");
const hoverhead = (r) => `<b>${esc(r.en)}</b> · ${esc(r.fr)} · <i>${esc(r.sci)}</i><br>` +
  `${r.group}, tier ${r.tier}, ${Math.round(r.birds).toLocaleString("en")} birds per season`;

// --- rows ---------------------------------------------------------------------
function passes(f, key) {  // the filter `f` (state or draft), for the figure of `key`
  const g = new Set(f.group), k = new Set(f.rank), t = new Set(f.tier), c = new Set(f.cls);
  const q = f.name.trim().toLowerCase();
  return (r) => r[key] && g.has(r.group) && k.has(r.rank) && t.has(r.tier) && c.has(r[key].cls)
    && (!q || [r.en, r.fr, r.sci].some((n) => String(n).toLowerCase().includes(q)));
}
function filtered(key) {
  return DATA.filter(passes(state, key)).map((r) => Object.assign({}, r, {cls: r[key].cls}));
}
function sorted(rows, how, value) {  // top row first; returned bottom-up, as Plotly draws y
  const by = {
    value: (a, b) => value(a) - value(b),
    order: (a, b) => a.order - b.order,
    birds: (a, b) => b.birds - a.birds,
    name: (a, b) => a.en.localeCompare(b.en),
    group: (a, b) => a.group.localeCompare(b.group) || value(a) - value(b),
  }[how] || ((a, b) => value(a) - value(b));
  return rows.slice().sort(by).reverse();
}

// --- marks --------------------------------------------------------------------
// colour: the group; symbol: the class (filled shown, hollow caveated, small grey hidden,
// diamond from counts)
function markers(rows, shape = "circle", size = 8) {
  return {
    symbol: rows.map((r) => r.cls === "counts" ? "diamond" : shape),
    color: rows.map((r) => r.cls === "hide" ? HIDE_FILL : r.cls === "caveat" ? PAPER : GROUPS[r.group]),
    line: {width: rows.map((r) => r.cls === "hide" ? 1 : 1.6), color: rows.map((r) => r.cls === "hide" ? HIDE_LINE : GROUPS[r.group])},
    size: rows.map((r) => r.cls === "hide" ? size - 3 : r.cls === "counts" ? size + 1 : size),
  };
}
function segments(rows, lo, hi, y = (r, i) => i) {  // one trace of segments, rows split by null
  const x = [], yy = [];
  rows.forEach((r, i) => { if (lo(r) != null && hi(r) != null) { x.push(lo(r), hi(r), null); yy.push(y(r, i), y(r, i), null); } });
  return {x, y: yy};
}
function glyphSvg(cls, color = MUTED, shape = "circle") {
  const s = 12, c = 6;
  let el;
  if (cls === "counts") el = `<path d="M6 1L11 6L6 11L1 6Z" fill="${color}"/>`;
  else if (cls === "hide") el = `<circle cx="6" cy="6" r="3" fill="${HIDE_FILL}" stroke="${HIDE_LINE}"/>`;
  else {
    const fill = cls === "show" ? color : PAPER;
    el = shape === "circle" ? `<circle cx="6" cy="6" r="4.5" fill="${fill}" stroke="${color}" stroke-width="1.6"/>`
      : shape === "triangle-left" ? `<path d="M1.5 6L10.5 1.5L10.5 10.5Z" fill="${fill}" stroke="${color}" stroke-width="1.4"/>`
      : `<path d="M10.5 6L1.5 1.5L1.5 10.5Z" fill="${fill}" stroke="${color}" stroke-width="1.4"/>`;
  }
  return `<svg class="gl" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" aria-hidden="true">${el}</svg>`;
}
const keyItem = (mark, text) => `<span>${mark}${esc(text)}</span>`;
const lineMark = (c, w = 2) => `<span class="ln" style="border-top:${w}px solid ${c}"></span>`;
const boxMark = (c, o = 1) => `<span class="bx" style="background:${c};opacity:${o}"></span>`;
function key(id, items) { document.getElementById(id).innerHTML = items.join(""); }

// --- layout -------------------------------------------------------------------
function labels(rows, note = () => "") {
  return rows.map((r) => {
    const n = esc(r.en) + note(r);
    if (r.id === state.sel) return `<b>${n}</b>`;
    return r.cls === "hide" ? `<span style="color:${HIDE_LINE}">${n}</span>` : n;
  });
}
function layout(rows, xaxis, opts = {}) {
  const n = rows.length, mirror = n > MIRROR_ROWS, domain = opts.glyphs ? [0.035, 1] : [0, 1];
  const shapes = [];
  const i = rows.findIndex((r) => r.id === state.sel);
  if (i >= 0) shapes.push({type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: i - 0.5, y1: i + 0.5,
    fillcolor: SELECT, line: {width: 0}, layer: "below"});
  if (opts.groupLines) rows.forEach((r, k) => { if (k > 0 && r.group !== rows[k - 1].group)
    shapes.push({type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: k - 0.5, y1: k - 0.5, line: {color: ZERO, width: 1, dash: "dot"}}); });
  const x = Object.assign({side: "top", gridcolor: GRID, zeroline: false, tickangle: 0, domain, fixedrange: true,
    tickfont: {size: 11, color: MUTED}, title: {font: {size: 12, color: MUTED}}}, xaxis);
  const lay = {
    font: {family: "system-ui, -apple-system, sans-serif", color: INK, size: 12}, paper_bgcolor: PAPER, plot_bgcolor: PAPER,
    height: TOP + (mirror ? BOTTOM + 30 : BOTTOM) + Math.max(n, 3) * ROW, showlegend: false,
    margin: {l: 8, r: 24, t: TOP, b: mirror ? BOTTOM + 30 : BOTTOM}, hovermode: "closest",
    hoverlabel: {align: "left", bgcolor: PAPER, bordercolor: ZERO, font: {color: INK, size: 12}},
    yaxis: {tickvals: rows.map((r, k) => k), ticktext: opts.labels || labels(rows), range: [-0.6, Math.max(n, 1) - 0.4],
            automargin: true, tickfont: {size: 11}, fixedrange: true, showgrid: false, zeroline: false,
            anchor: "free", position: 0},
    xaxis: x, shapes,
  };
  if (opts.glyphs) lay.xaxis2 = {domain: [0, 0.025], range: [0, 1], visible: false, fixedrange: true};
  if (mirror) lay.xaxis3 = Object.assign({}, x, {side: "bottom", overlaying: "x", matches: "x", title: {text: ""}, showgrid: false});
  return lay;
}
function extras(rows, opts = {}) {  // glyph column (heat maps) and the anchor of the bottom axis
  const out = [];
  if (opts.glyphs) out.push({type: "scatter", mode: "markers", xaxis: "x2", x: rows.map(() => 0.5), y: rows.map((r, k) => k),
    marker: markers(rows), customdata: rows.map((r) => r.id), text: rows.map((r) => `${hoverhead(r)}<br>${opts.glyphs}: ${why(r[opts.key])}`),
    hovertemplate: "%{text}<extra></extra>"});
  if (rows.length > MIRROR_ROWS) out.push({type: "scatter", mode: "markers", xaxis: "x3", x: [opts.anchor], y: [0], marker: {opacity: 0}, hoverinfo: "skip"});
  return out;
}
const CONFIG = {responsive: true, displaylogo: false, modeBarButtonsToRemove: ["select2d", "lasso2d", "zoom2d", "pan2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"],
  toImageButtonOptions: {format: "svg"}};
function draw(id, traces, lay, rows, countId, total) {
  const el = document.getElementById(id);
  document.getElementById(countId).textContent = `${rows.length} of ${total} taxa`;
  if (!rows.length) { Plotly.purge(el); el.innerHTML = '<p class="empty">No taxon matches the filters.</p>'; return; }
  if (!el.classList.contains("js-plotly-plot")) el.innerHTML = "";
  Plotly.react(el, traces, lay, CONFIG);
  if (!el._bound) {
    el._bound = true;
    el.on("plotly_click", (e) => {
      const p = e.points[0], c = Array.isArray(p.customdata) ? null : p.customdata;
      const id = c || (p.data.customdata && p.data.customdata[p.pointIndex[0]]) || null;
      if (id) select(id === state.sel ? null : id);
    });
  }
}

// --- 1. abundance trend -------------------------------------------------------
function trendFig() {
  const total = DATA.filter((r) => r.trend).length;
  const perYear = state.t.unit === "year";
  const v = (r, x = r.trend.log) => perYear ? x / (r.trend.last - r.trend.first) : x;
  let rows = sorted(filtered("trend"), state.t.sort, (r) => v(r));
  const late = (r) => r.trend.first > YEARS[0] ? `<span style="color:${ZERO}"> · ${r.trend.first}</span>` : "";
  if (state.t.view === "heat") {
    const years = []; for (let y = YEARS[0]; y <= YEARS[1]; y++) years.push(y);
    const z = rows.map((r) => years.map((y) => { const i = r.trend.years.indexOf(y); return i < 0 ? null : r.trend.rel[i]; }));
    const text = rows.map((r) => years.map((y) => { const i = r.trend.years.indexOf(y); if (i < 0) return "";
      const x = r.trend.rel[i]; return `${hoverhead(r)}<br>${y}: <b>${x >= 0 ? "×" + Math.pow(2, x).toFixed(2) : "÷" + Math.pow(2, -x).toFixed(2)}</b> the taxon's mean<br>trend: ${why(r.trend)}`; }));
    const trace = {type: "heatmap", x: years, y: rows.map((r, k) => k), z, text, hovertemplate: "%{text}<extra></extra>",
      customdata: rows.map((r) => years.map(() => r.id)), zmin: -3, zmax: 3, zmid: 0, xgap: 1, ygap: 1,
      colorscale: [[0, "#a83a24"], [0.25, "#e0a493"], [0.5, "#f4f1ea"], [0.75, "#9cb8cf"], [1, "#2f5878"]],
      colorbar: {orientation: "h", y: 1, yanchor: "top", yref: "container", x: 1, xanchor: "right", len: 260, lenmode: "pixels", thickness: 8,
        tickvals: [-3, -2, -1, 0, 1, 2, 3], ticktext: ["÷8", "÷4", "÷2", "mean", "×2", "×4", "×8"], tickfont: {size: 10, color: MUTED}}};
    key("t-key", [keyItem(boxMark("#a83a24"), "below the taxon's mean"), keyItem(boxMark("#2f5878"), "above"),
      keyItem(boxMark("#f4f1ea"), "near the mean"), keyItem("", "column on the left: group and class of the trend")]);
    const lay = layout(rows, {dtick: 4, range: [YEARS[0] - 0.5, YEARS[1] + 0.5], title: {text: ""}}, {glyphs: "trend", labels: labels(rows, late), groupLines: state.t.sort === "group"});
    lay.margin.t = TOP + 30;
    draw("fig-trend", [trace, ...extras(rows, {glyphs: "trend", key: "trend", anchor: YEARS[0]})], lay, rows, "t-count", total);
    return;
  }
  const fmt = (lr) => perYear ? pct(lr) + "/yr" : pct(lr);
  const ticks = (perYear ? [-0.1, -0.05, 0, 0.05, 0.1, 0.2] : [-0.9, -0.5, 0, 1, 9, 49]).map((c) => Math.log1p(c));
  const w = segments(rows, (r) => r.trend.lo == null ? null : v(r, r.trend.lo), (r) => r.trend.hi == null ? null : v(r, r.trend.hi));
  const traces = [
    {type: "scatter", mode: "lines", x: w.x, y: w.y, line: {color: "rgba(98,92,83,0.55)", width: 1.5}, hoverinfo: "skip"},
    {type: "scatter", mode: "markers", x: rows.map((r) => v(r)), y: rows.map((r, k) => k), marker: markers(rows), customdata: rows.map((r) => r.id),
     text: rows.map((r) => `${hoverhead(r)}<br><b>${pct(r.trend.log)}</b> ${r.trend.first}–${r.trend.last}` +
       (r.trend.lo == null ? "" : ` (95%, conservative: ${pct(r.trend.lo)} to ${pct(r.trend.hi)})`) +
       `<br>${pct(r.trend.log / (r.trend.last - r.trend.first))} per year · smooth total ${Math.round(r.trend.s0).toLocaleString("en")} → ${Math.round(r.trend.s1).toLocaleString("en")}` +
       `<br>trend: ${why(r.trend)}`), hovertemplate: "%{text}<extra></extra>"},
  ];
  const lay = layout(rows, {tickvals: ticks, ticktext: ticks.map(fmt), zeroline: true, zerolinecolor: ZERO, zerolinewidth: 1.5,
    title: {text: (perYear ? "change per year" : "change, first to last trend year (log scale)") + "   ← decline · increase →"}},
    {labels: labels(rows, late), groupLines: state.t.sort === "group"});
  key("t-key", [keyItem(lineMark("rgba(98,92,83,0.55)"), "95% interval (conservative)"),
    keyItem(`<span style="color:${ZERO}">· 2007</span>`, "trend starts later than " + YEARS[0])]);
  draw("fig-trend", [...traces, ...extras(rows, {anchor: ticks[0]})], lay, rows, "t-count", total);
}

// --- 2. passage dates ---------------------------------------------------------
function passageFig() {
  const total = DATA.filter((r) => r.passage).length;
  const how = state.p.sort;
  const val = {q10: (r) => r.passage.q10, q90: (r) => r.passage.q90, span: (r) => r.passage.q90 - r.passage.q10}[how] || ((r) => r.passage.q50);
  const rows = sorted(filtered("passage"), ["q10", "q50", "q90", "span"].includes(how) ? "value" : how, val);
  const xaxis = {tickvals: DOY_TICKS, ticktext: DOY_TICKS.map(date), range: [180, 336], title: {text: ""}};
  const head = (r) => `${hoverhead(r)}<br>10% ${date(r.passage.q10)} · <b>50% ${date(r.passage.q50)}</b> · 90% ${date(r.passage.q90)}` +
    (r.passage.q50_lo != null ? `<br>${r.passage.year} median, modelled: 80% band ${date(r.passage.q50_lo)} to ${date(r.passage.q50_hi)}` : "") +
    `<br>${r.passage.source === "smooth" ? `smooth season of ${r.passage.year}` : `counted seasons ${r.passage.from}–${r.passage.to} pooled`} · ${why(r.passage)}`;
  const groupLines = how === "group";
  if (state.p.view === "heat") {
    const doy = []; for (let d = 180; d <= 336; d++) doy.push(d);
    const z = rows.map((r) => doy.map((d) => { if (!r.passage.density) return null; const i = d - r.passage.doy[0]; return i >= 0 && i < r.passage.density.length ? r.passage.density[i] : null; }));
    const trace = {type: "heatmap", x: doy, y: rows.map((r, k) => k), z, zmin: 0, zmax: 1, ygap: 1,
      colorscale: [[0, "#faf8f2"], [0.15, "#e6edf3"], [0.4, "#9cb8cf"], [0.7, "#3d6a8f"], [1, "#1f3b52"]],
      customdata: rows.map((r) => doy.map(() => r.id)), text: rows.map((r) => doy.map((d) => head(r) + `<br>${date(d)}`)),
      hovertemplate: "%{text}<br>%{z:.0%} of the peak day<extra></extra>",
      colorbar: {orientation: "h", y: 1, yanchor: "top", yref: "container", x: 1, xanchor: "right", len: 200, lenmode: "pixels", thickness: 8, tickformat: ".0%", tickfont: {size: 10, color: MUTED}}};
    const med = {type: "scatter", mode: "markers", x: rows.map((r) => r.passage.q50), y: rows.map((r, k) => k),
      marker: {symbol: "line-ns", size: 11, line: {width: 2, color: "#d9a92e"}}, hoverinfo: "skip"};
    key("p-key", [keyItem(boxMark("#1f3b52"), "share of the season, against the taxon's peak day"), keyItem(lineMark("#d9a92e"), "median date"),
      keyItem("", "column on the left: group and class of the dates")]);
    const lay = layout(rows, xaxis, {glyphs: "dates", groupLines});
    lay.margin.t = TOP + 30;
    draw("fig-passage", [trace, med, ...extras(rows, {glyphs: "dates", key: "passage", anchor: 200})], lay, rows, "p-count", total);
    return;
  }
  const traces = [];
  for (const [g, c] of Object.entries(GROUPS)) {
    const s = segments(rows, (r) => r.group === g ? r.passage.q10 : null, (r) => r.passage.q90);
    traces.push({type: "scatter", mode: "lines", x: s.x, y: s.y, line: {color: c, width: 7}, opacity: 0.3, hoverinfo: "skip"});
  }
  const s = segments(rows, (r) => r.passage.q50_lo, (r) => r.passage.q50_hi);
  traces.push({type: "scatter", mode: "lines", x: s.x, y: s.y, line: {color: INK, width: 1.5}, hoverinfo: "skip"});
  traces.push({type: "scatter", mode: "markers", x: rows.map((r) => r.passage.q50), y: rows.map((r, k) => k),
    marker: markers(rows), customdata: rows.map((r) => r.id), text: rows.map(head), hovertemplate: "%{text}<extra></extra>"});
  key("p-key", [keyItem(boxMark(MUTED, 0.35), "10% to 90% of the season passed"), keyItem(glyphSvg("show"), "median date"),
    keyItem(lineMark(INK, 1.5), "80% band of the median (with a trend)")]);
  draw("fig-passage", [...traces, ...extras(rows, {anchor: 200})], layout(rows, xaxis, {groupLines}), rows, "p-count", total);
}

// --- 3. passage shift ---------------------------------------------------------
const QSHAPE = {q10: "triangle-left", q50: "circle", q90: "triangle-right"};
const QNAME = {q10: "10%", q50: "median", q90: "90%"};
function shiftFig() {
  const total = DATA.filter((r) => r.shift).length;
  const all = state.s.q === "all", main = all ? "q50" : state.s.q, qs = all ? ["q10", "q50", "q90"] : [main];
  const unit = (r, d) => state.s.unit === "decade" ? 10 * d / (r.shift.last - r.shift.first) : d;
  const how = state.s.sort;
  const rows = sorted(filtered("shift"), how === "q50" ? "value" : how,
    how === "q50" ? (r) => r.passage ? r.passage.q50 : r.shift.q50.to : (r) => unit(r, r.shift[main].d));
  const off = all ? {q10: 0.27, q50: 0, q90: -0.27} : {[main]: 0};
  const traces = [];
  for (const q of qs) {
    const y = (r, i) => i + off[q];
    const w = segments(rows, (r) => unit(r, r.shift[q].lo), (r) => unit(r, r.shift[q].hi), y);
    traces.push({type: "scatter", mode: "lines", x: w.x, y: w.y, line: {color: "rgba(98,92,83,0.55)", width: all ? 1 : 1.5}, hoverinfo: "skip"});
    traces.push({type: "scatter", mode: "markers", x: rows.map((r) => unit(r, r.shift[q].d)), y: rows.map(y),
      marker: markers(rows, QSHAPE[q], all ? 7 : 8), customdata: rows.map((r) => r.id),
      text: rows.map((r) => { const s = r.shift[q]; return `${hoverhead(r)}<br>${QNAME[q]} date ${date(s.from)} (${r.shift.first}) → ${date(s.to)} (${r.shift.last})<br>` +
        `<b>${signed(s.d, 1)} days</b> (95%: ${signed(s.lo, 1)} to ${signed(s.hi, 1)}) · ${signed(10 * s.d / (r.shift.last - r.shift.first), 1)} days per decade<br>season: ${why(r.shift)}`; }),
      hovertemplate: "%{text}<extra></extra>"});
  }
  const lay = layout(rows, {zeroline: true, zerolinecolor: ZERO, zerolinewidth: 1.5, ticksuffix: " d",
    title: {text: (state.s.unit === "decade" ? "days per decade" : "days, first to last year") + "   ← earlier · later →"}},
    {groupLines: how === "group"});
  key("s-key", [keyItem(lineMark("rgba(98,92,83,0.55)"), "95% interval"),
    ...(all ? [keyItem(glyphSvg("show", MUTED, "triangle-left"), "10% date (upper)"), keyItem(glyphSvg("show"), "median"),
               keyItem(glyphSvg("show", MUTED, "triangle-right"), "90% date (lower)")] : [])]);
  draw("fig-shift", [...traces, ...extras(rows, {anchor: 0})], lay, rows, "s-count", total);
}

// --- selection card -----------------------------------------------------------
function card() {
  const el = document.getElementById("card"), r = DATA.find((d) => d.id === state.sel);
  if (!r) { el.hidden = true; return; }
  const row = (name, c, text) => c ? `<dt>${name}</dt><dd>${glyphSvg(c.cls, GROUPS[r.group])} ${text}<br><span class="note" style="margin:0">${why(c)}</span></dd>` : "";
  const t = r.trend, p = r.passage, s = r.shift;
  const guide = (sec) => `../index.html?species=${encodeURIComponent(r.id)}#${sec}`;
  el.innerHTML = `<button class="close" type="button" aria-label="Close">×</button>
    <h4>${esc(r.en)}</h4><div class="sub">${esc(r.fr)} · <i>${esc(r.sci)}</i><br>
    <span class="sw" style="background:${GROUPS[r.group]}"></span> ${r.group} · tier ${r.tier} · ${Math.round(r.birds).toLocaleString("en")} birds per season</div><dl>
    ${row("Trend", t, t && `<b>${pct(t.log)}</b> ${t.first}–${t.last}, ${pct(t.log / (t.last - t.first))}/yr`)}
    ${row("Passage", p, p && `${date(p.q10)} · <b>${date(p.q50)}</b> · ${date(p.q90)}`)}
    ${row("Shift", s, s && `median <b>${signed(s.q50.d, 1)} d</b> ${s.first}–${s.last}`)}
    </dl><div class="links">${r.page ? `Methods guide: <a href="${guide(GUIDE.trend)}">trend</a> <a href="${guide(GUIDE.passage)}">dates</a> <a href="${guide(GUIDE.shift)}">shift</a><br>
    <a href="../qa/index.html#${encodeURIComponent(r.id)}">QA row</a>` : ""}
    <a href="${EXPLORE}${encodeURIComponent(r.id)}" target="_blank" rel="noopener">defile-website ↗</a></div>`;
  el.querySelector(".close").addEventListener("click", () => select(null));
  el.hidden = false;
}
function select(id) { state.sel = id; writeUrl(); all(); card(); }

// --- filters: edited in the panel, applied together --------------------------
const LABEL = {cls: CLS_NAME, rank: {species: "species", other: "sp., slash, hybrid"}};
const panel = document.getElementById("f-panel"), toggle = document.getElementById("f-toggle");
function draft() {
  const f = {name: document.getElementById("f-name").value};
  for (const k of SETS) f[k] = [...document.querySelectorAll(`#f-${k} input:checked`)].map((i) => i.value);
  return f;
}
function syncFilters() {
  for (const k of SETS) document.querySelectorAll(`#f-${k} input`).forEach((e) => { e.checked = state[k].includes(e.value); });
  document.getElementById("f-name").value = state.name;
}
function summary() {
  const part = (k, title) => {
    const all = document.querySelectorAll(`#f-${k} input`).length;
    const v = state[k].length === all ? "all" : state[k].map((x) => (LABEL[k] || {})[x] || x).join(", ");
    return `${title} <b>${esc(v)}</b>`;
  };
  const n = new Set(["trend", "passage", "shift"].flatMap((key) => filtered(key).map((r) => r.id))).size;
  document.getElementById("f-summary").innerHTML = `<b>${n} taxa</b> · ` +
    [part("group", "group"), part("rank", "taxa"), part("tier", "tier"), part("cls", "on defile-website")].join(" · ") +
    (state.name ? ` · name <b>“${esc(state.name)}”</b>` : "");
}
const same = (a, b) => SETS.every((k) => a[k].slice().sort().join() === b[k].slice().sort().join()) && a.name.trim() === b.name.trim();
function preview() {  // what Apply would draw, figure by figure
  const f = draft(), out = document.getElementById("f-preview"), apply = document.getElementById("f-apply");
  const empty = SETS.filter((k) => !f[k].length);
  document.querySelectorAll(".f-grid fieldset").forEach((fs) => fs.classList.toggle("empty", empty.includes(fs.id.slice(2))));
  if (empty.length) {
    out.className = "warn"; out.textContent = "Tick at least one box in each list.";
    apply.disabled = true; return;
  }
  const n = (key) => DATA.filter(passes(f, key)).length;
  out.className = ""; out.textContent = `Apply draws: trend ${n("trend")} · passage dates ${n("passage")} · shift ${n("shift")} taxa`;
  apply.disabled = same(f, state);
}
function openPanel(open) {
  panel.hidden = !open; toggle.setAttribute("aria-expanded", String(open));
  if (open) { syncFilters(); preview(); }
}
toggle.addEventListener("click", () => openPanel(panel.hidden));
panel.addEventListener("input", preview);
panel.addEventListener("submit", (e) => {
  e.preventDefault();
  if (document.getElementById("f-apply").disabled && !same(draft(), state)) return;
  Object.assign(state, draft()); state.name = state.name.trim();
  openPanel(false); writeUrl(); all(); summary();
});
document.getElementById("f-cancel").addEventListener("click", () => openPanel(false));
document.querySelectorAll(".f-grid fieldset[id]").forEach((fs) => {  // all · none, for lists of 3+
  if (fs.querySelectorAll("input").length < 3) return;
  const qs = document.createElement("span"); qs.className = "qs";
  qs.innerHTML = '<button type="button" data-v="1">all</button> · <button type="button" data-v="">none</button>';
  qs.addEventListener("click", (e) => { if (e.target.tagName !== "BUTTON") return;
    fs.querySelectorAll("input").forEach((i) => { i.checked = !!e.target.dataset.v; }); preview(); });
  fs.querySelector("legend").appendChild(qs);
});

// --- figure controls: immediate -----------------------------------------------
function all() { trendFig(); passageFig(); shiftFig(); }
function syncControls() {
  for (const [id, fig, prop] of [["t-view", "t", "view"], ["t-unit", "t", "unit"], ["p-view", "p", "view"], ["s-q", "s", "q"], ["s-unit", "s", "unit"]])
    document.querySelectorAll(`#${id} button`).forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === state[fig][prop])));
  for (const f of ["t", "p", "s"]) document.getElementById(`${f}-sort`).value = state[f].sort;
  document.querySelector("#t-unit").hidden = state.t.view === "heat";
}
const REDRAW = {t: trendFig, p: passageFig, s: shiftFig};
for (const [id, fig, prop] of [["t-view", "t", "view"], ["t-unit", "t", "unit"], ["p-view", "p", "view"], ["s-q", "s", "q"], ["s-unit", "s", "unit"]])
  document.querySelectorAll(`#${id} button`).forEach((b) => b.addEventListener("click", () => {
    state[fig][prop] = b.dataset.v; syncControls(); writeUrl(); REDRAW[fig]();
  }));
for (const f of ["t", "p", "s"]) document.getElementById(`${f}-sort`).addEventListener("change", (e) => { state[f].sort = e.target.value; writeUrl(); REDRAW[f](); });
document.getElementById("reset").addEventListener("click", () => {
  Object.assign(state, JSON.parse(JSON.stringify(DEFAULTS))); syncFilters(); syncControls(); openPanel(false);
  writeUrl(); all(); card(); summary();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!panel.hidden) openPanel(false); else if (state.sel) select(null);
});
readUrl(); syncFilters(); syncControls(); all(); card(); summary();
"""

DEFAULTS = {  # the page's view without URL parameters
    "group": list(GROUPS),
    "tier": ["full"],
    "rank": ["species"],
    "cls": ["show", "caveat", "counts"],
    "name": "",
    "sel": None,
    "t": {"view": "dots", "unit": "total", "sort": "value"},
    "p": {"view": "range", "sort": "q50"},
    "s": {"q": "q50", "unit": "total", "sort": "value"},
}


def compare_page(data: list, manifest: dict | None = None) -> str:
    checkbox = lambda name, value, mark, label: (  # noqa: E731
        f'<label><input type="checkbox" name="{name}" value="{value}">{mark}{label}</label>'
    )
    groups = "".join(
        checkbox("group", g, f'<span class="sw" style="background:{c}"></span>', g)
        for g, c in GROUPS.items()
    )
    tiers = "".join(checkbox("tier", t, "", label) for t, label in TIERS)
    ranks = "".join(checkbox("rank", r, "", label) for r, label in RANKS)
    classes = "".join(checkbox("cls", c, glyph(c), label) for c, label in CLASS_LABELS)
    glyphs = ", ".join(f"{glyph(c)} {label}" for c, label in CLASS_LABELS)
    years = [y for r in data if r["trend"] for y in r["trend"]["years"]]
    body = (
        BODY.replace("__GROUPS__", groups)
        .replace("__TIERS__", tiers)
        .replace("__RANKS__", ranks)
        .replace("__CLASSES__", classes)
        .replace("__GLYPHS__", glyphs)
        .replace("__FIRST__", str(min(years, default="")))
        .replace("__LAST__", str(max(years, default="")))
        .replace("__KEY_YEARS__", str(KEY_YEARS))
        .replace("__DATA__", json.dumps(data, separators=(",", ":"), allow_nan=False))
        .replace("__GROUP_COLORS__", json.dumps(GROUPS))
        .replace("__GUIDE__", json.dumps(GUIDE))
        .replace("__EXPLORE__", json.dumps(EXPLORE))
        .replace("__DEFAULTS__", json.dumps(DEFAULTS))
        .replace("__JS__", JS)
    )
    return wrap("Species comparison", f"<style>{CSS}</style>{body}", manifest, current="compare")


def write(export: str, out: str) -> str:
    """Write the comparison as `out/index.html`, its own page and URL (`compare/`)."""
    taxa = json.load(open(os.path.join(export, "taxa.json")))
    manifest = json.load(open(os.path.join(export, "manifest.json")))
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(compare_page(rows(taxa, export), manifest))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export", default=os.path.join(ROOT, "data", EXPORT_DIR))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "output", "site", "compare"))
    args = ap.parse_args(argv)
    print("->", write(args.export, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
