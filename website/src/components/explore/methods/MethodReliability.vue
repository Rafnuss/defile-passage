<template>
  <p>
    We hide observations from well-counted seasons using gaps from older counting schedules, refit
    the daily model, and reconstruct the hidden passage. We compare the reconstructed season total
    with the birds originally counted. This tests recovery within observed counting periods; it
    cannot check birds that were never observed.
  </p>
  <figure v-if="trials.length" class="figure w-100">
    <div ref="plotDiv" class="validation-plot"></div>
    <div class="validation-metrics">
      <span
        ><strong>{{ trials.length }}</strong> trials</span
      >
      <span
        >Typical error <strong>{{ error }}%</strong></span
      >
      <span
        >Truth inside 80% interval <strong>{{ Math.round(100 * gap.cover80) }}%</strong></span
      >
    </div>
    <figcaption class="figure-caption">
      <strong>Figure 5.1.</strong> {{ name }}: reconstructed totals (blue dots; predictive medians)
      against originally counted totals. Black lines show 80% intervals, with thinner 95%
      extensions. Each of the {{ targets }} test seasons is masked several times, each time with the
      gaps of a different historical season, so several dots can share one originally counted total
      (one vertical line). The diagonal marks perfect agreement. Typical error is the median
      absolute log error, expressed as a percentage difference.
    </figcaption>
  </figure>
  <p v-else>No gap-transplant validation is available for {{ name }}.</p>
  <details v-if="trials.length" class="method-detail">
    <summary>What is held out, and what remains fixed?</summary>
    <p>
      Recent, well-counted seasons receive the partial-day and full-day gaps of historical
      schedules. The coefficients are refitted after masking; smoothing parameters and dispersion
      retain their full-fit values. The reference is passage within the original counting coverage.
      The test therefore assesses reconstruction under those settings, rather than a completely
      independent refit of every model parameter.
    </p>
    <p>
      Published totals use predictive means; this benchmark scores predictive medians. These
      seasonal-total tests do not directly validate the phenology slopes. Display decisions also
      consider coverage, interval widths and the boundaries of the counting season.
    </p>
  </details>
  <p>
    <a :href="`./qa/index.html#${data.taxon_id}`"
      >Inspect {{ name }}’s show / caveat / hide decisions in the QA table →</a
    >
  </p>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS } from "../../../theme";
const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});
const trials = computed(() => props.data.benchmark?.gap_trials ?? []);
const gap = computed(() => props.data.benchmark?.gap);
const targets = computed(() => new Set(trials.value.map((r) => r.target)).size);
const error = computed(() => Math.round(100 * Math.expm1(gap.value.abs_log_err)));
const plotDiv = ref(null),
  visible = usePlot(plotDiv);
function plot() {
  if (!visible.value || !trials.value.length) return;
  const t = trials.value;
  const bounds = [
    Math.max(1, Math.min(...t.map((r) => Math.min(r.truth, r["q2.5"])))),
    Math.max(...t.map((r) => Math.max(r.truth, r["q97.5"]))),
  ];
  plotReact(
    plotDiv.value,
    [
      {
        x: bounds,
        y: bounds,
        mode: "lines",
        name: "Perfect agreement",
        line: { color: COLORS.faint, dash: "dot" },
        hoverinfo: "skip",
      },
      ...[
        ["q2.5", "q97.5", 1, "95% interval"],
        ["q10", "q90", 3, "80% interval"],
      ].map(([lo, hi, width, name]) => ({
        x: t.flatMap((r) => [r.truth, r.truth, null]),
        y: t.flatMap((r) => [r[lo], r[hi], null]),
        mode: "lines",
        name,
        line: { color: COLORS.ink, width },
        hoverinfo: "skip",
      })),
      {
        x: t.map((r) => r.truth),
        y: t.map((r) => r.estimate),
        mode: "markers",
        name: "Reconstructed total",
        marker: { color: COLORS.predicted, size: 7 },
        text: t.map((r) => `${r.target} · gaps from ${r.donor}`),
        hovertemplate:
          "%{text}<br>Originally counted: %{x:,.0f}<br>Reconstructed median: %{y:,.0f}<extra></extra>",
      },
    ],
    {
      margin: { t: 60, l: 65, r: 20, b: 55 },
      legend: { orientation: "h", x: 0.5, xanchor: "center", y: 1.2, font: { size: 10 } },
      xaxis: { type: "log", title: { text: "Originally counted birds" }, fixedrange: true },
      yaxis: { type: "log", title: { text: "Reconstructed birds" }, fixedrange: true },
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(() => [visible.value, props.data], plot);
</script>
<style scoped>
.validation-plot {
  height: 400px;
}
.validation-metrics {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  font-size: 0.85rem;
  margin: 0.5rem 0;
}
</style>
