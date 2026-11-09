<template>
  <figure class="figure w-100 widget">
    <div class="d-flex justify-content-between align-items-center small mb-2 gap-2">
      <YearSelector id="episode-year" v-model="year" :years="years" context="episode" />
    </div>
    <div ref="plotDiv" class="plot"></div>
    <figcaption class="figure-caption">
      <strong>Figure 2.6.</strong> {{ name }}, {{ year }}: coverage-adjusted counts (points),
      baseline expectation (grey dashed), then weather (pink) and weather plus episodes (orange).
      Lower panels show their multipliers. Each legend label gives the cumulative percentage of
      count-model deviance explained for this season, relative to a constant full-day passage rate.
    </figcaption>
    <p class="metric-note">
      All percentages use the same counted days and constant-rate reference. They describe fit to
      these observations, not independent contributions or performance on new data.
    </p>
  </figure>
</template>

<script setup>
import YearSelector from "./YearSelector.vue";
import { ref, computed, watch } from "vue";
import { usePlot, plotReact } from "../../utils/usePlot";
import { COLORS, alpha } from "../../theme.js";
import { doyLabel } from "../../services/explore";

const props = defineProps({
  name: { type: String, required: true },
  theta: { type: Number, required: true },
  minCoverage: { type: Number, required: true },
  // trend.episodes: {doy, base: {year: [...]}, weather: {year: [...]}, episode: {year: [...]}},
  // weather and episode as log multipliers of base (defile-passage `trend.episode_curves`)
  episodes: { type: Object, required: true },
  // the species' days, columnar: {date: [...], count: [...], c: [...]}
  days: { type: Object, required: true },
});

const C_EPISODE = COLORS.ochre;
const C_WEATHER = COLORS.pink;
const C_BASE = alpha(COLORS.ink, 0.6);
const C_POINT = alpha(COLORS.counted, 0.65);
const DATE_TICKS = [213, 244, 274, 305];
const FACTOR_TICKS = [0.25, 0.5, 1, 2, 4];

const years = computed(() => Object.keys(props.episodes.base).map(Number));
const year = ref(years.value.at(-1));
watch(years, (ys) => !ys.includes(year.value) && (year.value = ys.at(-1)));

// a year's log multipliers (an export from before the weather has none: zeros)
const logs = (y) => {
  const ep = props.episodes.episode[y];
  return { wx: props.episodes.weather?.[y] ?? ep.map(() => 0), ep };
};

// Season day on the model’s non-leap calendar
const doyOf = (s) => {
  const [, m, d] = s.split("-").map(Number);
  return (Date.UTC(2001, m - 1, d) - Date.UTC(2001, 0, 1)) / 86400000 + 1;
};

// The counted days the model fits: {year: Map(doy -> {n, c})}
const counted = computed(() => {
  const { date, count, c } = props.days;
  const [d0, d1] = [props.episodes.doy[0], props.episodes.doy.at(-1)];
  const out = {};
  date.forEach((s, i) => {
    const y = +s.slice(0, 4);
    const t = doyOf(s);
    if (!(y in props.episodes.base) || t < d0 || t > d1 || !(c[i] >= props.minCoverage)) return;
    (out[y] ??= new Map()).set(t, { n: count[i], c: c[i] });
  });
  return out;
});

const explained = computed(() => {
  const y = String(year.value),
    doy = props.episodes.doy;
  const base = props.episodes.base[y],
    { wx, ep } = logs(y);
  const points = counted.value[y] ?? new Map();
  if (!points.size || [...points.values()].every((r) => r.n === 0)) return null;
  // Maximum-likelihood constant full-day rate under the same NB likelihood and coverage.
  const score = (rate) =>
    [...points.values()].reduce(
      (sum, r) => sum + (r.n - r.c * rate) / (props.theta + r.c * rate),
      0,
    );
  let lo = 0,
    hi = Math.max(...[...points.values()].map((r) => r.n / r.c)) + 1;
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2;
    if (score(mid) > 0) lo = mid;
    else hi = mid;
  }
  const rate = (lo + hi) / 2;
  const deviance = (mean) =>
    doy.reduce((sum, t, i) => {
      const r = points.get(t);
      if (!r) return sum;
      const mu = Math.max(r.c * mean(i), 1e-12),
        n = r.n,
        th = props.theta;
      return (
        sum + 2 * ((n > 0 ? n * Math.log(n / mu) : 0) - (n + th) * Math.log((n + th) / (mu + th)))
      );
    }, 0);
  const nullDeviance = deviance(() => rate);
  return nullDeviance > 0
    ? {
        base: 100 * (1 - deviance((i) => base[i]) / nullDeviance),
        weather: 100 * (1 - deviance((i) => base[i] * Math.exp(wx[i])) / nullDeviance),
        full: 100 * (1 - deviance((i) => base[i] * Math.exp(wx[i] + ep[i])) / nullDeviance),
      }
    : null;
});
const metricLabel = (label, key) =>
  explained.value ? `${label} · ${explained.value[key].toFixed(0)}% deviance explained` : label;
const plotDiv = ref(null);
const visible = usePlot(plotDiv);

function draw() {
  if (!visible.value || !plotDiv.value) return;
  const y = String(year.value);
  const { doy } = props.episodes;
  const base = props.episodes.base[y];
  const { wx, ep } = logs(y);
  const fWx = wx.map(Math.exp);
  const fEp = ep.map(Math.exp);
  const pts = [...(counted.value[y] ?? new Map()).entries()];
  const xaxis = {
    fixedrange: true,
    range: [doy[0] - 1, doy.at(-1) + 1],
    tickvals: DATE_TICKS,
    ticktext: DATE_TICKS.map((d) => doyLabel(d, "en")),
  };
  plotReact(
    plotDiv.value,
    [
      {
        x: pts.map(([t]) => t),
        y: pts.map(([, p]) => p.n / p.c),
        mode: "markers",
        marker: { color: C_POINT, size: 5 },
        name: "counted / coverage",
        customdata: pts.map(([t, p]) => [doyLabel(t, "en"), p.n, Math.round(p.c * 100)]),
        hovertemplate:
          "%{customdata[0]}: %{customdata[1]:,} counted, %{customdata[2]}% covered<extra></extra>",
      },
      {
        x: doy,
        y: base,
        mode: "lines",
        line: { color: C_BASE, width: 1.5, dash: "dash" },
        name: metricLabel("Season + year", "base"),
        hoverinfo: "skip",
      },
      {
        x: doy,
        y: base.map((b, i) => b * fWx[i]),
        mode: "lines",
        line: { color: C_WEATHER, width: 1.5 },
        name: metricLabel("Weather", "weather"),
        hovertemplate: "%{y:,.0f} with the weather<extra></extra>",
      },
      {
        x: doy,
        y: base.map((b, i) => b * fWx[i] * fEp[i]),
        mode: "lines",
        line: { color: C_EPISODE, width: 2 },
        name: metricLabel("Weather + episodes", "full"),
        hovertemplate: "%{y:,.0f} expected<extra></extra>",
      },
      {
        x: doy,
        y: fWx,
        mode: "lines",
        line: { color: C_WEATHER, width: 1.5 },
        xaxis: "x2",
        yaxis: "y2",
        showlegend: false,
        hovertemplate: "weather ×%{y:.2f}<extra></extra>",
      },
      {
        x: doy,
        y: fEp,
        mode: "lines",
        line: { color: C_EPISODE, width: 1.5 },
        xaxis: "x2",
        yaxis: "y2",
        showlegend: false,
        hovertemplate: "episodes ×%{y:.2f}<extra></extra>",
      },
    ],
    {
      margin: { t: 45, l: 56, r: 8, b: 32 },
      dragmode: false,
      autosize: true,
      font: { size: 11 },
      legend: { orientation: "h", x: 0, y: 1.2, font: { size: 10 } },
      xaxis: { ...xaxis, matches: "x2", showticklabels: false, anchor: "y" },
      yaxis: {
        domain: [0.4, 1],
        fixedrange: true,
        rangemode: "tozero",
        title: { text: "birds per full day" },
      },
      xaxis2: { ...xaxis, anchor: "y2" },
      yaxis2: {
        domain: [0, 0.32],
        type: "log",
        fixedrange: true,
        tickvals: FACTOR_TICKS,
        ticktext: FACTOR_TICKS.map((v) => `×${v}`),
        title: { text: "×" },
      },
      shapes: [
        {
          type: "line",
          xref: "x2 domain",
          x0: 0,
          x1: 1,
          yref: "y2",
          y0: 1,
          y1: 1,
          line: { color: alpha(COLORS.ink, 0.35), width: 1, dash: "dot" },
        },
      ],
    },
    { displayModeBar: false, responsive: true },
  );
}

watch(() => [visible.value, year.value, props.episodes, counted.value], draw);
</script>

<style scoped>
.widget {
  border: 1px solid var(--bs-border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
}
.plot {
  min-height: 380px;
}
</style>
