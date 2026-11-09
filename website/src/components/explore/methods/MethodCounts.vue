<template>
  <div>
    <section id="counts-m-species">
      <h5><span class="sec-n">1</span>Which species</h5>
      <slot name="species" />
    </section>
    <section id="counts-m-history">
      <h5><span class="sec-n">2</span>Which years</h5>
      <p>
        Migration has been counted at the Défilé since <strong>1966</strong>. In the early decades,
        counts covered only a few days or hours each season. Daily, systematic counting began in
        <strong>1993</strong>, and most passerines were recorded in full from <strong>2007</strong>.
        Hourly counts followed in <strong>2014</strong>, with entry on Trektellen from
        <strong>2021</strong>. We adapt the start year of each species to its recording history:
        generally 1993 for the original target groups, or 2007 for species recorded systematically
        later. For {{ name }}, we use counts from <strong>{{ startYear }}</strong> onward
        {{ data.trend ? "in the model" : "for comparisons between seasons" }}.
        <template v-if="data.settings.start_year.source === 'override'">{{
          data.settings.start_year.reason
        }}</template>
      </p>
      <figure v-if="effort" class="figure w-100">
        <div ref="historyDiv" class="plot-sm"></div>
        <figcaption class="figure-caption">
          <strong>Figure 1.1.</strong> Days counted each season between 18 July and 18 November, all
          species; in colour, the seasons compared for {{ name }}.
        </figcaption>
      </figure>
    </section>

    <section id="counts-m-window">
      <h5><span class="sec-n">3</span>Which days?</h5>
      <p>
        Every species is modelled over the same dates, <strong>{{ windowText }}</strong
        >. Counts are generally conducted from 18 July to 18 November, but the passage of some
        species starts before and continues after, and counting often also takes place then. As we
        are interested in total numbers, we extend the period to the dates counted in at least one
        season in three since 1993, averaged over a week.
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS } from "../../../theme.js";

const { locale } = useI18n();

const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
  lastCompleteYear: { type: Number, required: true },
});

const PROTOCOL = {
  1993: "daily counts",
  2007: "passerines",
  2014: "hour by hour",
  2021: "Trektellen",
};

const startYear = computed(() => props.data.settings.start_year.value);
const lastYear = computed(() => props.lastCompleteYear);
// "MM-DD" -> "18 Jul" in the locale
const md = (mmdd) => {
  const [m, d] = mmdd.split("-").map(Number);
  return new Date(Date.UTC(2001, m - 1, d)).toLocaleDateString(locale.value, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
};
const windowText = computed(() => props.data.window.model.map(md).join(" – "));
const historyDiv = ref(null);
const visible = usePlot(historyDiv);

function plotHistory() {
  if (!visible.value || !historyDiv.value || !props.effort) return;
  const e = props.effort.filter((r) => r.year <= lastYear.value);
  plotReact(
    historyDiv.value,
    [
      {
        x: e.map((r) => r.year),
        y: e.map((r) => r.window_days),
        type: "bar",
        marker: {
          color: e.map((r) => (r.year >= startYear.value ? COLORS.muted : COLORS.historyInner)),
        },
        hovertemplate: "%{x}: %{y} days<extra></extra>",
      },
    ],
    {
      margin: { t: 34, l: 40, r: 8, b: 28 },
      dragmode: false,
      autosize: true,
      showlegend: false,
      font: { size: 11 },
      xaxis: { fixedrange: true },
      yaxis: { fixedrange: true, title: { text: "days" } },
      shapes: Object.keys(PROTOCOL).map((y) => ({
        type: "line",
        x0: y - 0.5,
        x1: y - 0.5,
        yref: "paper",
        y0: 0,
        y1: 1,
        line: { color: COLORS.muted, dash: "dot", width: 1 },
      })),
      annotations: Object.entries(PROTOCOL).map(([y, text], k) => ({
        x: y - 0.5,
        y: 1.02 + 0.1 * (k % 2),
        yanchor: "bottom",
        yref: "paper",
        text,
        showarrow: false,
        xanchor: "right",
        font: { size: 10, color: COLORS.muted },
      })),
    },
    { displayModeBar: false, responsive: true },
  );
}

watch(() => [visible.value, props.effort, startYear.value], plotHistory);
</script>
