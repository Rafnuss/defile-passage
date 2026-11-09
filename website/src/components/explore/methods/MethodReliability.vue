<template>
  <section id="reliability-m-test">
    <h5><span class="sec-n">1</span>Can the model recover counts it did not see?</h5>
    <p>
      We take recent, well-counted seasons and hide the hours and days that an older season did not
      count, so that the recent season has the older one’s gaps. We refit the model without the
      hidden counts, reconstruct the season, and compare its total with the birds that were actually
      counted. Each recent season is tested with the gaps of several older ones.
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
        <strong>Figure 5.1.</strong> {{ name }}: reconstructed season totals (blue dots; predictive
        medians) against the birds counted. Each season has one dot per older season whose gaps it
        was given, on the same vertical line. Black lines show 80% intervals, with thinner 95%
        extensions; the diagonal marks perfect agreement. Typical error is the median absolute log
        error, expressed as a percentage difference.
      </figcaption>
    </figure>
    <p v-else>No gap test is available for {{ name }}.</p>
    <p v-if="trials.length">
      The test refits the coefficients only; the smoothing parameters and <Tex e="\theta" /> keep
      their values from the full fit. It checks the reconstruction within the days counted; it
      cannot check birds that passed when no season was counted. It scores predictive medians, while
      the totals published on the species pages are predictive means.
    </p>
  </section>
  <section id="reliability-m-classes">
    <h5><span class="sec-n">2</span>When is a result shown?</h5>
    <p>
      Each result resting on the model is shown, shown with a caveat, or hidden. The season totals
      are judged mainly by the test above: a caveat when the typical error exceeds 16%, hidden above
      49%. A caveat is also added when the 80% intervals hold the truth in fewer than 60% of trials,
      when less than 60% of a typical season’s total was counted, when the intervals are wide, or
      when the passage continues beyond regular counting. The long-term trend needs the totals and a
      95% band that is not too wide; the passage dates need narrow bands and at least 50 birds in a
      typical season. Change over the years (the long-term trend and the shift in passage dates) is
      hidden for passerines, counted systematically only from 2008 and with growing attention since,
      so that their change follows the counting effort more than the birds; and for groups of
      species (“sp.”), whose numbers follow how many birds were identified. Their seasons and
      passage dates are still shown.
    </p>
    <table v-if="data.reliability" class="table table-sm small">
      <thead>
        <tr>
          <th>{{ name }}</th>
          <th>Shown</th>
          <th>Why</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="claim in CLAIMS" :key="claim.key">
          <td>{{ claim.label }}</td>
          <td>{{ CLASS_WORDS[data.reliability[claim.key].class] }}</td>
          <td>
            {{
              data.reliability[claim.key].reasons
                .map((r) => r.code.replaceAll("_", " "))
                .join(", ") || "all checks passed"
            }}
          </td>
        </tr>
      </tbody>
    </table>
    <p>
      <a :href="`./qa/index.html#${data.taxon_id}`"
        >See every species’ decisions in the QA table →</a
      >
    </p>
  </section>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS } from "../../../theme";
import Tex from "../Tex.vue";

const CLAIMS = [
  { key: "totals", label: "Season totals" },
  { key: "trend", label: "Long-term trend" },
  { key: "season", label: "Passage dates" },
];
const CLASS_WORDS = { show: "yes", caveat: "with a caveat", hide: "no" };
const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});
const trials = computed(() => props.data.benchmark?.gap_trials ?? []);
const gap = computed(() => props.data.benchmark?.gap);
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
