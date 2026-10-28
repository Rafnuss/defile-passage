<template>
  <figure class="figure w-100 widget">
    <div class="small mb-2">
      <label class="form-label mb-0 d-flex justify-content-between">
        <span>Smoothing parameter, <Tex e="\rho_k" /></span>
        <strong><Tex :e="lambdaTex" /></strong>
      </label>
      <input
        v-model.number="logLambda"
        type="range"
        class="form-range"
        :min="LOG_LAMBDA[0]"
        :max="LOG_LAMBDA[1]"
        step="0.05"
      />
      <div class="d-flex justify-content-between text-muted range-ends">
        <span>follows every year</span>
        <span>straight line</span>
      </div>
    </div>

    <div class="readout small">
      The curve uses about <strong>{{ edf.toFixed(1) }}</strong> effective parameters for
      {{ y.length }} years: {{ edfWords }}
    </div>

    <div ref="plotDiv" class="plot"></div>
    <figcaption class="figure-caption">
      <strong>Figure 2.7.</strong> A penalised smooth (blue) through {{ name }}'s estimated season
      totals (points), on the log scale, for the <Tex e="\rho_k" /> chosen above. The penalty uses
      squared second differences, favouring a straight line on the log scale as smoothing increases.
      It shows the smoothing alone. The model's own trend is not one of these curves: it is fitted
      to the daily counts together with the other terms, not to these totals.
    </figcaption>
  </figure>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { usePlot, plotReact } from "../../utils/usePlot";
import { COLORS } from "../../theme.js";
import Tex from "./Tex.vue";

const props = defineProps({
  name: { type: String, required: true },
  // trend.annual: [{year, total, ...}]
  annual: { type: Array, required: true },
});

const LOG_LAMBDA = [-2, 6];
const C_TREND = COLORS.predicted;
const C_POINT = COLORS.ink;

const logLambda = ref(1);
const lambda = computed(() => 10 ** logLambda.value);
const lambdaTex = computed(() => {
  const l = logLambda.value;
  return Math.abs(l - Math.round(l)) < 0.03 ? `10^{${Math.round(l)}}` : `10^{${l.toFixed(1)}}`;
});

const years = computed(() => props.annual.map((r) => r.year));
const y = computed(() => props.annual.map((r) => Math.log(Math.max(r.total, 1))));

/**
 * Whittaker smoother, a P-spline with one coefficient per year: minimises
 * |y - z|^2 + lambda |D2 z|^2, so z = (I + lambda D2'D2)^-1 y. Returns z and the effective degrees
 * of freedom, the trace of that inverse (the hat matrix).
 */
function smooth(yv, lam) {
  const n = yv.length;
  // A = I + lam * D2'D2, a symmetric pentadiagonal matrix (dense here: n is about 30)
  const A = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => +(i === j)));
  for (let k = 0; k + 2 < n; k++) {
    const d = [1, -2, 1];
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) A[k + a][k + b] += lam * d[a] * d[b];
  }
  // Gauss-Jordan on [A | I | y]: the inverse for the trace, and z
  const M = A.map((row, i) => [...row, ...row.map((_, j) => +(i === j)), yv[i]]);
  for (let c = 0; c < n; c++) {
    const piv = M[c][c];
    for (let j = 0; j <= 2 * n; j++) M[c][j] /= piv;
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c];
      if (f) for (let j = 0; j <= 2 * n; j++) M[r][j] -= f * M[c][j];
    }
  }
  return { z: M.map((row) => row[2 * n]), edf: M.reduce((s, row, i) => s + row[n + i], 0) };
}

const fit = computed(() => smooth(y.value, lambda.value));

const edf = computed(() => fit.value.edf);
const edfWords = computed(() => {
  const e = edf.value;
  const n = y.value.length;
  if (e > n * 0.6) return "almost one per year, so it copies the good and bad years.";
  if (e < 2.3) return "two would be a straight line, a constant rate of change.";
  return "a smooth curve that bends over several years.";
});

// 1, 2, 5, 10, 20, ... within the data's range, for a log axis without crowded minor labels
function ticks125(values) {
  const lo = Math.min(...values.filter((v) => v > 0));
  const hi = Math.max(...values);
  const out = [];
  for (let m = 10 ** Math.floor(Math.log10(lo)); m <= hi * 10; m *= 10)
    for (const f of [1, 2, 5]) if (f * m >= lo / 2 && f * m <= hi * 2) out.push(f * m);
  return out;
}

const plotDiv = ref(null);
const visible = usePlot(plotDiv);

function draw() {
  if (!visible.value || !plotDiv.value) return;
  const yr = years.value;
  plotReact(
    plotDiv.value,
    [
      {
        x: yr,
        y: props.annual.map((r) => r.total),
        mode: "markers",
        marker: { color: C_POINT, size: 6 },
        name: "Estimated total",
        hovertemplate: "%{x}: %{y:,.0f}<extra></extra>",
      },
      {
        x: yr,
        y: fit.value.z.map(Math.exp),
        mode: "lines",
        line: { color: C_TREND, width: 3 },
        name: "Smooth",
        hovertemplate: "%{x}: %{y:,.0f}<extra>smooth</extra>",
      },
    ],
    {
      margin: { t: 24, l: 56, r: 8, b: 32 },
      dragmode: false,
      autosize: true,
      font: { size: 11 },
      legend: { orientation: "h", x: 1, xanchor: "right", y: 1.15 },
      xaxis: { fixedrange: true },
      yaxis: {
        type: "log",
        title: { text: "birds per season" },
        fixedrange: true,
        tickvals: ticks125(props.annual.map((r) => r.total)),
      },
    },
    { displayModeBar: false, responsive: true },
  );
}

watch(() => [visible.value, fit.value, props.annual], draw);
</script>

<style scoped>
.widget {
  border: 1px solid var(--bs-border-color);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
}
.readout {
  background: var(--bs-light);
  border-radius: 0.375rem;
  padding: 0.4rem 0.6rem;
}
.range-ends {
  font-size: 0.75rem;
  margin-top: -0.4rem;
}
.plot {
  min-height: 260px;
}
</style>
