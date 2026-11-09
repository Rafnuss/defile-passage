<template>
  <div>
    <section id="shown-m-dates">
      <h5><span class="sec-n">1</span>Passage dates</h5>
      <p>
        We describe a season’s phenology by the dates when <strong>10%</strong>,
        <strong>50%</strong> (the median) and <strong>90%</strong> of its birds have passed.
        Expressing passage as a fraction of that year’s total makes timing comparable across years
        with different numbers of birds.
      </p>
      <p v-if="filled">
        We use gap-filled daily passage so that missing counting periods do not shift these dates
        towards better-counted parts of the season. We calculate all three dates separately in each
        of the model’s 1 000 reconstructed seasons; their variation gives uncertainty in each date.
      </p>
      <p v-else>
        This taxon’s displayed seasonal series uses coverage-adjusted counts and interpolation
        across missing days. Its dates do not have model-based reconstruction intervals.
      </p>
      <figure class="figure w-100">
        <div class="d-flex justify-content-between align-items-center small mb-2 gap-2">
          <span class="text-muted">One season, day by day</span>
          <YearSelector id="phenology-year" v-model="year" :years="years" context="phenology" />
        </div>
        <div ref="seasonDiv" class="plot-md"></div>
        <figcaption class="figure-caption">
          <strong>Figure 4.1.</strong> {{ name }}, {{ year }}: daily passage shares ({{
            filled ? "blue" : "red"
          }}) and cumulative passage (black).
          <template v-if="filled"
            >Grey curves show 50 of 1 000 conditional reconstructions, with 80% date bands for the
            10%, 50% and 90% thresholds. These illustrative draws hold the exported daily
            predictions fixed and exclude coefficient uncertainty; reported passage dates use the
            full reconstruction draws.</template
          ><template v-else>Missing days are interpolated for the cumulative curve.</template>
        </figcaption>
      </figure>
    </section>
    <section id="phenology-m-trend">
      <h5><span class="sec-n">2</span>Change in phenology</h5>
      <p v-if="s.phenology?.quantiles?.q50">
        We quantify change in phenology by fitting a straight line to each season’s 10%, 50% and 90%
        passage dates. We repeat the fit in each of the 1 000 joint reconstructions, keeping one
        date per year in each fit, and resample the remaining variation between years to estimate
        trend uncertainty.
      </p>
      <p v-else>No model-based phenology trend is available for {{ name }}.</p>
      <figure class="figure w-100">
        <PassageDateTrend :records="s.passage" :trends="s.phenology?.quantiles ?? {}" />
        <figcaption class="figure-caption">
          <strong>Figure 4.2.</strong> Annual passage dates with 80% reconstruction intervals, and
          linear trends with 95% uncertainty bands. The legend gives the estimated change in days
          per decade.
        </figcaption>
      </figure>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS, PASSAGE_COLORS, alpha } from "../../../theme.js";
import YearSelector from "../YearSelector.vue";
import PassageDateTrend from "../PassageDateTrend.vue";
import { gammaSampler } from "../../../utils/simulation";
import { doyLabel } from "../../../services/explore";

const { locale } = useI18n();

const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});

const s = computed(() => props.data.season);
// From the trend's gap-filled days (defile-passage `season.source`), else from the counts
const filled = computed(() => s.value.source === "gam");
const years = computed(() => s.value.years.slice().reverse());
const year = ref(years.value[0]);
watch(years, (ys) => !ys.includes(year.value) && (year.value = ys[0]));

const passage = computed(() => {
  const p = s.value.passage.find((r) => r.year === year.value);
  if (!p || p.q50 == null) return null;
  return { ...p, dates: ["q10", "q50", "q90"].map((k) => doyLabel(p[k], locale.value)).join(", ") };
});

// "MM-DD" -> day of year in a non-leap year
const doyOf = (mmdd) => {
  const [m, d] = mmdd.split("-").map(Number);
  return Math.round((Date.UTC(2001, m - 1, d) - Date.UTC(2001, 0, 1)) / 86400000) + 1;
};

// The season's running total over the model window (as defile-passage season.py sums it), blank
// days on the straight line between their counted neighbours; null outside the window
function running(share, doy) {
  const [w0, w1] = props.data.window.model.map(doyOf);
  const inWindow = doy.map((d) => d >= w0 && d <= w1);
  const v = share.map((x, i) => (inWindow[i] ? x : 0));
  const known = v.map((x, i) => (inWindow[i] && x != null ? i : -1)).filter((i) => i >= 0);
  for (let i = 0; i < v.length; i++) {
    if (v[i] != null) continue;
    const a = known.filter((k) => k < i).at(-1);
    const b = known.find((k) => k > i);
    v[i] = a == null ? (v[b] ?? 0) : b == null ? v[a] : v[a] + ((v[b] - v[a]) * (i - a)) / (b - a);
  }
  const total = v.reduce((t, x) => t + x, 0) || 1;
  let c = 0;
  return v.map((x, i) => ((c += x / total), inWindow[i] ? c : null));
}

const conditional = computed(() => {
  if (!filled.value || !props.data.trend) return null;
  const t = props.data.trend,
    d = t.days,
    e = t.episodes;
  const indices = d.date
    .map((date, i) => (date.startsWith(`${year.value}-`) ? i : -1))
    .filter((i) => i >= 0);
  const doy = indices.map((i) => doyOf(d.date[i].slice(5)));
  const rates = doy.map((day) => {
    const j = e.doy.indexOf(day);
    return e.base[year.value][j] * Math.exp(e.weather[year.value][j] + e.episode[year.value][j]);
  });
  const { gamma, poisson } = gammaSampler(26031 + year.value);
  const dates = [[], [], []],
    curves = [];
  for (let draw = 0; draw < 1000; draw++) {
    const counts = indices.map((i, j) => {
      const c = d.c[i] >= t.min_coverage ? d.c[i] : 0;
      if (c === 1) return d.count[i];
      const lambda = gamma(t.theta + (c > 0 ? d.count[i] : 0)) / (t.theta / rates[j] + c);
      return d.count[i] + poisson((gamma(t.kappa * (1 - c)) * lambda) / t.kappa);
    });
    const total = counts.reduce((a, b) => a + b, 0);
    if (!total) continue;
    let sum = 0;
    const curve = counts.map((v) => (sum += v / total));
    if (draw < 50) curves.push(curve);
    [0.1, 0.5, 0.9].forEach((q, j) => {
      const i = curve.findIndex((v) => v >= q);
      const previous = i ? curve[i - 1] : 0;
      dates[j].push(doy[i] - 1 + (q - previous) / (curve[i] - previous));
    });
  }
  return {
    doy,
    curves,
    bands: dates.map((values) => {
      values.sort((a, b) => a - b);
      return [values[Math.floor(values.length * 0.1)], values[Math.floor(values.length * 0.9)]];
    }),
  };
});
const seasonDiv = ref(null);
const visible = usePlot(seasonDiv);

function plot() {
  if (!visible.value || !seasonDiv.value) return;
  const i = s.value.years.indexOf(year.value);
  const share = s.value.share[i];
  const doy = s.value.doy;
  const ticks = [196, 213, 227, 244, 258, 274, 288, 305, 319, 335].filter(
    (d) => d >= doy[0] && d <= doy.at(-1),
  );
  const p = passage.value;
  plotReact(
    seasonDiv.value,
    [
      ...(conditional.value
        ? [
            {
              x: conditional.value.curves.flatMap(() => [...conditional.value.doy, null]),
              y: conditional.value.curves.flatMap((curve) => [...curve, null]),
              yaxis: "y2",
              mode: "lines",
              line: { color: alpha(COLORS.faint, 0.3), width: 1 },
              hoverinfo: "skip",
              name: "Possible cumulative passage",
              showlegend: true,
            },
          ]
        : []),
      {
        x: doy,
        y: share.map((v) => (v == null ? null : v)),
        type: "bar",
        name: "Daily passage",
        // a day nobody counted, its share estimated by the model
        marker: { color: alpha(filled.value ? COLORS.predicted : COLORS.counted, 0.6) },
        text: doy.map((d) => doyLabel(d, locale.value)),
        hovertemplate: "%{text}: %{y:.1%} of the season<extra></extra>",
      },
      {
        x: doy,
        y: share.map((v) => (v == null ? 0.004 : null)),
        type: "bar",
        showlegend: false,
        marker: { color: alpha(COLORS.faint, 0.5) },
        hoverinfo: "skip",
      },
      {
        x: doy,
        y: running(share, doy),
        yaxis: "y2",
        mode: "lines",
        name: "Cumulative passage",
        line: { color: COLORS.ink, width: 2 },
        hoverinfo: "skip",
      },
    ],
    {
      margin: { t: 75, l: 48, r: 44, b: 30 },
      dragmode: false,
      autosize: true,
      showlegend: true,
      legend: { orientation: "h", x: 0.5, xanchor: "center", y: 1.28, font: { size: 10 } },
      font: { size: 11 },
      bargap: 0.1,
      barmode: "overlay",
      xaxis: {
        fixedrange: true,
        tickvals: ticks,
        ticktext: ticks.map((d) => doyLabel(d, locale.value)),
      },
      yaxis: {
        fixedrange: true,
        tickformat: ".0%",
        title: { text: "share per day" },
      },
      yaxis2: {
        fixedrange: true,
        overlaying: "y",
        side: "right",
        range: [0, 1.02],
        tickvals: [0, 0.25, 0.5, 0.75, 1],
        tickformat: ".0%",
        showgrid: false,
      },
      shapes: p
        ? [
            ...["q10", "q50", "q90"].map((k, j) => ({
              type: "line",
              name: `${[10, 50, 90][j]}% passage`,
              showlegend: true,
              x0: p[k],
              x1: p[k],
              yref: "paper",
              y0: 0,
              y1: 1,
              line: { color: PASSAGE_COLORS[j], width: 1.5 },
            })),
            ...(conditional.value
              ? conditional.value.bands.map(([lo, hi], j) => ({
                  type: "rect",
                  x0: lo,
                  x1: hi,
                  yref: "paper",
                  y0: 0,
                  y1: 1,
                  fillcolor: alpha(PASSAGE_COLORS[j], 0.12),
                  line: { width: 0 },
                  layer: "below",
                }))
              : []),
          ]
        : [],
    },
    { displayModeBar: false, responsive: true },
  );
}

watch(() => [visible.value, year.value, s.value, locale.value, conditional.value], plot);
</script>
