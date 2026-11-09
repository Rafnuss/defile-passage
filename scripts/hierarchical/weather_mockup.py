"""A mock-up of the Explore page's weather section, from the broad panel's `W3` fits.

Run from the repository root after `weather_panel.py --arms W3` and `weather_patterns.py`: uv run
python scripts/hierarchical/weather_mockup.py

Writes `logs/hierarchical/panel/weather_mockup.html` (self-contained). Per species: each term's
effect for its contrast with its 95% interval and class; beside it, the counted days in bins of the
term, as birds over the usual for the date and year; the wind as a rose (5 m/s from each of eight
directions against calm, the direction and speed terms together), a petal faded when not clear and
marked when fewer than `MIN_SECTOR_DAYS` counted days had wind from that sector.

Classes (the rule proposed to `reliability.py`): `show` when clear on all years (interval excludes
1, at least `MIN_EFFECT`) and both halves (odd, even years) point the same way (wind: preferred
directions within `MAX_ANGLE`); `caveat` when clear but a half points the other way; `hide`
otherwise. `confirmed` when the halves are each clear and agree (`weather_patterns.status`).
"""

import json

import numpy as np
import pandas as pd
from weather_effects import WIND_SPEED, Z95, clear, per_unit
from weather_panel import BINS
from weather_patterns import GROUP_ORDER, GROUPS, MAX_ANGLE, PANEL

ARM = "W3"
BIN_ORDER = {term: labels for term, (_, labels) in BINS.items()}
OUT = PANEL / "weather_mockup.html"
MIN_SECTOR_DAYS = 20
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
TERMS = {  # term: (heading, contrast in words, evidence bins)
    "rain": ("Rain", "1 mm an hour all day, against a dry day", "rain"),
    "rain_yesterday": ("Rain the day before", "1 mm an hour all day before", "rain_yesterday"),
    "sunshine": ("Sunshine", "a sunny day against an overcast one", "sunshine"),
    "boundary_layer": ("Thermals", "air mixed 500 m higher", "boundary_layer"),
    "pressure_change": ("Rising pressure", "5 hPa higher than the day before", "pressure_change"),
    "temperature_anomaly": (
        "Cold day",
        "3 °C colder than usual for the date",
        "temperature_anomaly",
    ),
}


def same_way(row_all: pd.Series, halves: list[pd.Series], term: str) -> bool:
    if term == "wind_direction":
        return all(abs((h.origin - row_all.origin + 180) % 360 - 180) <= MAX_ANGLE for h in halves)
    return all(np.sign(h.log_effect) == np.sign(row_all.log_effect) for h in halves)


def rose(fit: pd.Series, sectors: pd.DataFrame) -> list[dict]:
    """5 m/s from each sector against calm: the direction and speed terms together."""
    (a, sa), (b, sb), (c, sc) = (
        per_unit(fit, k) for k in ("wind_u100", "wind_v100", "wind_speed")
    )
    days = sectors.set_index("bin").days if len(sectors) else pd.Series(dtype=float)
    out = []
    for k, name in enumerate(SECTORS):
        u, v = -np.sin(np.radians(45 * k)), -np.cos(np.radians(45 * k))
        log_effect = WIND_SPEED * (a * u + b * v + c)
        se = WIND_SPEED * np.sqrt((u * sa) ** 2 + (v * sb) ** 2 + sc**2)
        out.append(
            {
                "sector": name,
                "effect": float(np.exp(log_effect)),
                "lo": float(np.exp(log_effect - Z95 * se)),
                "hi": float(np.exp(log_effect + Z95 * se)),
                "clear": bool(clear(log_effect, se)),
                "days": int(days.get(name, 0)),
            }
        )
    return out


def main():
    effects = pd.read_csv(PANEL / "effects.csv")
    effects = effects[effects.arm.eq(ARM)]
    fits = pd.concat(pd.read_csv(p) for p in sorted(PANEL.glob("fits_*.csv")))
    fits = fits[fits.arm.eq(ARM) & fits.half.eq("all")].set_index("taxon_id")
    evidence = pd.read_csv(PANEL / f"evidence_{ARM}.csv")
    groups = pd.read_csv(GROUPS, sep="\t").set_index("family").group
    species = []
    for taxon, t in effects.groupby("taxon_id"):
        wide = t.set_index(["term", "half"])
        fit = fits.loc[taxon]
        cards = []
        for term in [*TERMS, "wind_direction", "wind_speed"]:
            if (term, "all") not in wide.index:
                continue
            r = wide.loc[(term, "all")]
            halves = [wide.loc[(term, h)] for h in ("odd", "even")]
            cls = "hide" if not r.clear else "show" if same_way(r, halves, term) else "caveat"
            card = {
                "term": term,
                "class": cls,
                "confirmed": bool(r.status == "replicated"),
                "effect": float(np.exp(r.log_effect)),
                "lo": float(np.exp(r.log_effect - Z95 * r.se)),
                "hi": float(np.exp(r.log_effect + Z95 * r.se)),
            }
            if term in TERMS:
                heading, contrast, bins = TERMS[term]
                e = evidence[evidence.taxon_id.eq(taxon) & evidence.term.eq(bins)]
                e = e.assign(order=e.bin.map(BIN_ORDER[bins].index)).sort_values("order")
                card |= {
                    "heading": heading,
                    "contrast": contrast,
                    "evidence": e[["bin", "days", "relative"]].to_dict("records"),
                }
            if term == "wind_direction":
                card["origin"] = float(r.origin)
            cards.append(card)
        sectors = evidence[evidence.taxon_id.eq(taxon) & evidence.term.eq("wind_sector")]
        species.append(
            {
                "name": fit.english_name,
                "group": groups[fit.family],
                "birds": float(fit.birds),
                "days": int(fit.counted_days),
                "first_year": int(fit.first_year),
                "effects": cards,
                "rose": rose(fit, sectors[sectors.bin.isin(SECTORS)]),
                "calm": sectors.set_index("bin").relative.get("calm"),
            }
        )
    species.sort(key=lambda s: (GROUP_ORDER.index(s["group"]), -s["birds"]))
    data = json.dumps(
        {"species": species, "groups": GROUP_ORDER, "terms": {k: v[0] for k, v in TERMS.items()}},
        allow_nan=False,
        default=lambda v: None,
    )
    OUT.write_text(TEMPLATE.replace("__DATA__", data))
    print(f"{len(species)} species -> {OUT}")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weather and passage</title>
<style>
:root{--bg:#fbfaf7;--card:#fff;--ink:#1f2328;--muted:#6b7280;--line:#e5e2db;--up:#c2452d;
--down:#2f6db3;--faint:#d9d6cf;--accent:#7a5c2e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16181c;--card:#1e2126;
--ink:#e8e6e1;--muted:#9aa0a8;--line:#30343a;--up:#e07a5f;--down:#6fa3e0;--faint:#3a3e45;
--accent:#d4a75a}}
:root[data-theme="dark"]{--bg:#16181c;--card:#1e2126;--ink:#e8e6e1;--muted:#9aa0a8;--line:#30343a;
--up:#e07a5f;--down:#6fa3e0;--faint:#3a3e45;--accent:#d4a75a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
.lede{color:var(--muted);margin:0 0 20px;max-width:70ch}
.tabs{display:flex;gap:8px;margin:12px 0 16px}.tabs button{border:1px solid var(--line);
background:var(--card);color:var(--ink);padding:6px 12px;border-radius:999px;cursor:pointer}
.tabs button.on{border-color:var(--accent);color:var(--accent);font-weight:600}
select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);
background:var(--card);color:var(--ink);max-width:100%}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}
.meta{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
.effect{display:grid;grid-template-columns:150px minmax(0,1fr) 210px;gap:10px;align-items:center;
padding:8px 0;border-top:1px solid var(--line)}
@media (max-width:560px){.effect{grid-template-columns:1fr}}
.effect .name{font-weight:600}.effect .contrast{color:var(--muted);font-size:12px}
.badge{display:inline-block;font-size:11px;padding:1px 6px;border-radius:999px;margin-left:4px;
border:1px solid var(--line);color:var(--muted)}
.badge.caveat{border-color:var(--accent);color:var(--accent)}
.value{font-variant-numeric:tabular-nums;font-size:13px}
svg text{fill:var(--muted);font-size:10px}
.hidden-list{color:var(--muted);font-size:13px;margin-top:8px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:6px;border-bottom:1px solid var(--line);
text-align:center}th:first-child,td:first-child{text-align:left}
.scroll{overflow-x:auto}
.legend{font-size:12px;color:var(--muted)}
</style></head><body><main>
<h1>Weather and passage</h1>
<p class="lede">How each species' counted passage at the Défilé goes with the day's weather, at the
same date: a model's association, not a cause. Counts mix birds passing and birds seen: a headwind
brings birds lower, deep thermals can lift them out of sight. Mock-up from 72 species, 1993–2025.</p>
<div class="tabs"><button id="t-species" class="on">One species</button>
<button id="t-groups">All species by group</button></div>
<section id="species-view">
<select id="pick" aria-label="Species"></select>
<div id="card"></div></section>
<section id="groups-view" hidden></section>
<p class="legend">Bars: the day's expected passage multiplied by this, with its 95% interval (log
scale, ×¼ to ×4). Shown only when clear (interval excludes ×1, at least ±10%) and the same in odd
and even years; “confirmed”: clear in each half on its own. Beside it: the counted days in each
class, as birds counted over the usual for the date and year (1 = usual), with the number of
days.</p>
<script>
const D=__DATA__;
const css=k=>getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const fmt=v=>v>=10?Math.round(v):v>=1?v.toFixed(1):v.toFixed(2);
const X=(v,w)=>w/2+Math.max(-1,Math.min(1,Math.log(v)/Math.log(4)))*w/2;
function bar(e,w=260){const c=e.effect>1?css('--up'):css('--down');
return `<svg width="100%" viewBox="0 0 ${w} 26" role="img" aria-label="x${fmt(e.effect)}">
<line x1="${w/2}" x2="${w/2}" y1="2" y2="24" stroke="${css('--line')}"/>
<line x1="${X(e.lo,w)}" x2="${X(e.hi,w)}" y1="13" y2="13" stroke="${c}" stroke-width="2"/>
<rect x="${Math.min(X(e.effect,w),w/2)}" y="7" width="${Math.abs(X(e.effect,w)-w/2)}" height="12"
fill="${c}" opacity=".35"/><circle cx="${X(e.effect,w)}" cy="13" r="4" fill="${c}"/></svg>`}
function evidence(ev){if(!ev||!ev.length)return'';const w=210,h=36,n=ev.length,bw=w/n-8;
return `<svg width="100%" viewBox="0 0 ${w} ${h+26}">`+ev.map((b,i)=>{const r=b.relative||0;
const y=Math.max(0,Math.min(h,h/2-Math.log(Math.max(r,1e-3))/Math.log(4)*h/2));
const c=r>1?css('--up'):css('--down');return `<rect x="${i*(bw+8)}" y="${Math.min(y,h/2)}"
width="${bw}" height="${Math.abs(y-h/2)||1}" fill="${c}" opacity=".7"/>
<text x="${i*(bw+8)+bw/2}" y="${h+11}" text-anchor="middle">${b.bin}</text>
<text x="${i*(bw+8)+bw/2}" y="${h+23}" text-anchor="middle">×${fmt(r)} · ${b.days} d</text>`}).join('')
+`<line x1="0" x2="${w}" y1="${h/2}" y2="${h/2}" stroke="${css('--line')}"/></svg>`}
function rose(s){const R=105,cx=150,cy=140,max=Math.log(4),one=0.55*R;
const petals=s.rose.map((p,k)=>{const a=(k*45-90)*Math.PI/180,l=Math.max(-1,Math.min(1,
Math.log(p.effect)/max));const rr=Math.max(4,one+l*(l>0?R-one:one));const few=p.days<${MIN_SECTOR_DAYS};
const c=p.effect>1?css('--up'):css('--down');const half=Math.PI/8.5;
const pts=[[cx,cy],[cx+rr*Math.cos(a-half),cy+rr*Math.sin(a-half)],[cx+rr*Math.cos(a+half),
cy+rr*Math.sin(a+half)]];return `<polygon points="${pts.map(q=>q.join(',')).join(' ')}"
fill="${c}" opacity="${p.clear&&!few?.75:.15}" stroke="${few?css('--muted'):'none'}"
stroke-dasharray="${few?'2 2':''}"><title>${p.sector}: x${fmt(p.effect)} (${fmt(p.lo)}–${fmt(p.hi)}),
${p.days} counted days with wind from ${p.sector}</title></polygon>
<text x="${cx+(R+20)*Math.cos(a)}" y="${cy+(R+20)*Math.sin(a)}" text-anchor="middle">${p.sector}</text>
<text x="${cx+(R+20)*Math.cos(a)}" y="${cy+(R+20)*Math.sin(a)+11}" text-anchor="middle"
style="fill:${p.clear&&!few?c:css('--muted')}">×${fmt(p.effect)}</text>`}).join('');
return `<svg width="100%" viewBox="0 0 300 310" role="img" aria-label="wind rose">
<circle cx="${cx}" cy="${cy}" r="${one}" fill="none" stroke="${css('--line')}"/>
<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${css('--line')}" stroke-dasharray="3 3"/>
${petals}<text x="150" y="292" text-anchor="middle">a 5 m/s wind from each side, against calm</text>
<text x="150" y="305" text-anchor="middle">solid circle ×1, dashed ×4; faded: not clear or few days</text></svg>`}
function card(s){const shown=s.effects.filter(e=>e.class!=='hide'&&D.terms[e.term]);
const hidden=s.effects.filter(e=>e.class==='hide'&&D.terms[e.term]).map(e=>D.terms[e.term]);
const wind=s.effects.filter(e=>e.term==='wind_direction'||e.term==='wind_speed');
const windShown=wind.some(e=>e.class!=='hide');const dir=s.effects.find(e=>e.term==='wind_direction');
const rows=shown.map(e=>`<div class="effect"><div><div class="name">${e.heading}
${e.class==='caveat'?'<span class="badge caveat">differs between years</span>':''}
${e.confirmed?'<span class="badge">confirmed</span>':''}</div><div class="contrast">${e.contrast}</div></div>
<div>${bar(e)}<div class="value">×${fmt(e.effect)} (${fmt(e.lo)}–${fmt(e.hi)})</div></div>
<div>${evidence(e.evidence)}</div></div>`).join('');
const windText=windShown&&dir?`Passage is highest with wind from about ${Math.round(dir.origin)}°
${dir.class==='caveat'?'(differs between years)':''}.`:'No clear association with the wind.';
return `<div class="card"><h2 style="margin-top:0">${s.name}</h2><div class="meta">${s.group} ·
${s.days} counted days since ${s.first_year} · ${Math.round(s.birds).toLocaleString()} birds</div>
<div class="grid"><div>${rows||'<p class="meta">No clear association with these weather terms.</p>'}
${hidden.length?`<div class="hidden-list">No clear association: ${hidden.join(', ')}.</div>`:''}</div>
<div><h2 style="margin-top:8px;font-size:15px">Wind</h2>${windShown?rose(s):''}
<p class="meta">${windText}</p></div></div></div>`}
function groups(){const terms=[...Object.keys(D.terms),'wind_direction'];
const head='<tr><th>Group</th>'+terms.map(t=>`<th>${D.terms[t]||'Wind direction'}</th>`).join('')+'</tr>';
const body=D.groups.map(g=>{const sp=D.species.filter(s=>s.group===g);if(!sp.length)return'';
return `<tr><td>${g} (${sp.length})</td>`+terms.map(t=>{const es=sp.map(s=>s.effects.find(e=>e.term===t))
.filter(e=>e&&e.class!=='hide');if(t==='wind_direction'){const o=es.map(e=>e.origin);if(!o.length)return'<td>–</td>';
const x=o.reduce((a,v)=>a+Math.sin(v*Math.PI/180),0),y=o.reduce((a,v)=>a+Math.cos(v*Math.PI/180),0);
const m=(Math.atan2(x,y)*180/Math.PI+360)%360;return `<td>${es.length} · from ${['N','NE','E','SE','S','SW','W','NW'][Math.round(m/45)%8]}</td>`}
const up=es.filter(e=>e.effect>1).length,down=es.length-up;
return `<td><span style="color:${css('--up')}">${up?up+'↑':''}</span>
<span style="color:${css('--down')}">${down?down+'↓':''}</span>${es.length?'':'–'}</td>`}).join('')+'</tr>'}).join('');
return `<div class="card"><p class="meta">Species with a shown effect, more (↑) or less (↓)
passage; for the wind, the mean preferred direction.</p><div class="scroll"><table>${head}${body}</table></div></div>`
+D.groups.map(g=>{const sp=D.species.filter(s=>s.group===g);return sp.length?`<h2>${g}</h2>`+sp.map(card).join(''):''}).join('')}
const pick=document.getElementById('pick');
D.species.forEach((s,i)=>pick.add(new Option(`${s.name} (${s.group})`,i)));
const show=()=>document.getElementById('card').innerHTML=card(D.species[pick.value]);
pick.onchange=show;show();
let drawn=false;
document.getElementById('t-species').onclick=e=>{species_view.hidden=false;groups_view.hidden=true;
e.target.classList.add('on');document.getElementById('t-groups').classList.remove('on')};
document.getElementById('t-groups').onclick=e=>{species_view.hidden=true;groups_view.hidden=false;
e.target.classList.add('on');document.getElementById('t-species').classList.remove('on');
if(!drawn){groups_view.innerHTML=groups();drawn=true}};
const species_view=document.getElementById('species-view'),groups_view=document.getElementById('groups-view');
</script></main></body></html>
""".replace(
    "${MIN_SECTOR_DAYS}", str(MIN_SECTOR_DAYS)
)


if __name__ == "__main__":
    main()
