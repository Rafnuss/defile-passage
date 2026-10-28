<template>
  <figure class="figure w-100 widget">
    <div class="row g-3 align-items-center small mb-2">
      <div class="col-sm-6">
        <label class="form-label mb-0 d-flex justify-content-between">
          <span>Expected observed count, <Tex e="\mu_d" /></span>
          <strong>{{ fmt(mu) }}</strong>
        </label>
        <input
          v-model.number="logMu"
          type="range"
          class="form-range"
          min="0"
          max="3.7"
          step="0.01"
        />
      </div>
      <div class="col-sm-6">
        <label class="form-label mb-0 d-flex justify-content-between">
          <span>
            Dispersion, <Tex e="\theta" />
            <button
              v-if="Math.abs(theta - speciesTheta) > 1e-9"
              type="button"
              class="btn btn-link btn-sm p-0 ms-1 align-baseline"
              @click="logTheta = Math.log10(speciesTheta)"
            >
              back to {{ name }}
            </button>
          </span>
          <strong>{{ theta < 10 ? theta.toFixed(2) : theta.toFixed(0) }}</strong>
        </label>
        <input
          v-model.number="logTheta"
          type="range"
          class="form-range"
          min="-1.3"
          max="2.3"
          step="0.01"
        />
        <div class="d-flex justify-content-between text-muted range-ends">
          <span>very variable days</span><span>close to Poisson</span>
        </div>
      </div>
    </div>

    <div class="readout small">
      For an expected observed count of <strong>{{ fmt(mu) }}</strong> birds, the central 80%
      prediction interval for the observed count runs from <strong>{{ fmt(q.lo) }}</strong> to
      <strong>{{ fmt(q.hi) }}</strong> (median {{ fmt(q.med) }}).
      <template v-if="p0 >= 0.005">
        On <strong>{{ pct(p0) }}</strong> of such days, no bird is counted.
      </template>
    </div>

    <div class="d-flex justify-content-end align-items-center gap-2 small mt-2">
      <span class="text-muted">Bins</span>
      <div class="btn-group btn-group-sm" role="group" aria-label="Bins">
        <button
          v-for="s in SCALES"
          :key="s.key"
          type="button"
          class="btn btn-outline-secondary"
          :class="{ active: scale === s.key }"
          @click="scale = s.key"
        >
          {{ s.label }}
        </button>
      </div>
    </div>
    <div ref="plotDiv" class="plot"></div>
    <figcaption class="figure-caption">
      <strong>Figure 2.2.</strong> Negative-binomial counts (bars; central 80% darker) and Poisson
      counts with the same mean (line). {{ name }}:
      <Tex :e="`\\theta = ${speciesTheta.toFixed(2)}`" />.
    </figcaption>
  </figure>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { usePlot, plotReact } from "../../utils/usePlot";
import { COLORS, alpha } from "../../theme.js";
import Tex from "./Tex.vue";

const props = defineProps({
  name: { type: String, required: true },
  speciesTheta: { type: Number, required: true },
});

const TAIL = 0.999; // the pmf is summed up to this quantile; the rest is not drawn
const LINEAR_BINS = 300;
const SCALES = [
  { key: "linear", label: "equal" },
  { key: "log", label: "widening" },
];
const C_NB = alpha(COLORS.predicted, 0.6);
const C_OUT = alpha(COLORS.predicted, 0.25); // bars outside the 80% range
const C_POIS = COLORS.ink;

const logMu = ref(2);
const scale = ref("linear");
const logTheta = ref(Math.log10(props.speciesTheta));
watch(
  () => props.speciesTheta,
  (t) => (logTheta.value = Math.log10(t)),
);
const mu = computed(() => Math.round(10 ** logMu.value));
const theta = computed(() => 10 ** logTheta.value);

const fmt = (x) => Math.round(x).toLocaleString("en");
const pct = (p) => (p < 0.1 ? `${(p * 100).toFixed(1)}%` : `${Math.round(p * 100)}%`);

// pmf by recurrence on the log scale, from k = 0 until the cumulative probability reaches `upTo`
function pmf(logP0, logStep, upTo, kMax = 2e6) {
  const p = [];
  let lp = logP0;
  let cum = 0;
  for (let k = 0; k < kMax && cum < upTo; k++) {
    const pk = Math.exp(lp);
    p.push(pk);
    cum += pk;
    lp += logStep(k);
  }
  return p;
}
const nbPmf = computed(() => {
  const m = mu.value;
  const th = theta.value;
  const r = Math.log(m / (th + m));
  return pmf(th * Math.log(th / (th + m)), (k) => Math.log((k + th) / (k + 1)) + r, TAIL);
});
const poisPmf = computed(() => {
  const m = mu.value;
  return pmf(-m, (k) => Math.log(m) - Math.log(k + 1), 0.9999);
});
const quantile = (p, level) => {
  let cum = 0;
  for (let k = 0; k < p.length; k++) {
    cum += p[k];
    if (cum >= level) return k;
  }
  return p.length - 1;
};
const q = computed(() => {
  const p = nbPmf.value;
  return {
    lo: quantile(p, 0.1),
    med: quantile(p, 0.5),
    hi: quantile(p, 0.9),
  };
});
const p0 = computed(() => nbPmf.value[0]);

const plotDiv = ref(null);
const visible = usePlot(plotDiv);

const nice = (x) => {
  const m = 10 ** Math.floor(Math.log10(x));
  return [1, 2, 5, 10].map((f) => f * m).find((v) => v >= x);
};
// Bin edges. Linear: equal bins of a round width, about LINEAR_BINS of them up to the 99th
// percentile. Log: 0, 1, 2-4, 5-9, 10-19, ... so a heavy tail and a narrow Poisson share one axis.
function edges(scale, kMax) {
  if (scale === "linear") {
    const w = Math.max(1, nice(kMax / LINEAR_BINS));
    return Array.from({ length: Math.ceil(kMax / w) + 1 }, (_, i) => i * w);
  }
  const e = [0, 1];
  for (let m = 1; e.at(-1) <= kMax; m *= 10) e.push(2 * m, 5 * m, 10 * m);
  while (e.at(-2) > kMax) e.pop();
  return e;
}
const binLabel = (a, b) =>
  b - a === 1 ? `${a}` : `${a.toLocaleString("en")}–${(b - 1).toLocaleString("en")}`;

function draw() {
  if (!visible.value || !plotDiv.value) return;
  const nb = nbPmf.value;
  const po = poisPmf.value;
  const linear = scale.value === "linear";
  const kMax = linear
    ? Math.max(quantile(nb, 0.99), po.length) + 1
    : Math.max(nb.length, po.length);
  const e = edges(scale.value, kMax);
  const bin = (p) => {
    const out = new Array(e.length - 1).fill(0);
    let i = 0;
    p.forEach((v, k) => {
      while (i < out.length - 1 && k >= e[i + 1]) i++;
      if (k < e.at(-1)) out[i] += v;
    });
    return out;
  };
  const labels = e.slice(0, -1).map((a, i) => binLabel(a, e[i + 1]));
  const w = e[1] - e[0];
  // linear: numeric x at the bin's centre (on the count scale), log: one category per bin
  const x = linear ? e.slice(0, -1).map((a) => a + (w - 1) / 2) : labels;
  const nbB = bin(nb);
  const poB = bin(po);
  const { lo, hi } = q.value;
  const inRange = e.slice(0, -1).map((a, i) => e[i + 1] - 1 >= lo && a <= hi);
  plotReact(
    plotDiv.value,
    [
      {
        x,
        y: nbB,
        type: "bar",
        width: linear ? w * 0.9 : undefined,
        customdata: labels,
        marker: { color: inRange.map((r) => (r ? C_NB : C_OUT)) },
        name: "Negative binomial",
        hovertemplate: "%{customdata} birds: %{y:.1%} of days<extra></extra>",
      },
      {
        x,
        y: poB,
        customdata: labels,
        mode: "lines+markers",
        line: { color: C_POIS, width: 1.5 },
        marker: { size: linear ? 3 : 5 },
        name: "Poisson",
        hovertemplate: "%{customdata} birds: %{y:.1%} of days<extra>Poisson</extra>",
      },
    ],
    {
      margin: { t: 24, l: 50, r: 8, b: 56 },
      bargap: 0.1,
      dragmode: false,
      autosize: true,
      font: { size: 11 },
      legend: { orientation: "h", x: 1, xanchor: "right", y: 1.15 },
      xaxis: linear
        ? {
            title: { text: `birds on the day (bins of ${w.toLocaleString("en")})` },
            fixedrange: true,
            range: [-w / 2, e.at(-1) - w / 2],
          }
        : { title: { text: "birds on the day" }, fixedrange: true, type: "category" },
      yaxis: {
        title: { text: "share of days" },
        tickformat: ".0%",
        fixedrange: true,
        range: [0, 1.1 * Math.max(...nbB, ...poB)],
      },
    },
    { displayModeBar: false, responsive: true },
  );
}

watch(() => [visible.value, mu.value, theta.value, scale.value], draw);
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
  min-height: 240px;
}
</style>
