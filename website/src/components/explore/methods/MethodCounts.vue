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
        <strong>2021</strong>.
      </p>
      <figure v-if="effort" class="figure w-100">
        <div ref="historyDiv" class="plot-sm"></div>
        <figcaption class="figure-caption">
          <strong>Figure 1.1.</strong> Days counted each season between 18 July and 18 November, all
          species; in colour, the seasons compared for {{ name }}.
        </figcaption>
      </figure>
      <p>
        The start year follows the species’ recording history: generally 1993 for the original
        target groups, or 2007 for species recorded systematically later. Earlier isolated sightings
        do not establish a comparable series. Only complete seasons enter these comparisons.
      </p>
      <div class="callout callout-info">
        For <strong>{{ name }}</strong
        >, we use counts from <strong>{{ startYear }}</strong> onward
        {{ data.trend ? "in the model" : "for comparisons between seasons" }}. Earlier counts remain
        in the raw data.
        <template v-if="data.settings.start_year.source === 'override'">{{
          data.settings.start_year.reason
        }}</template>
      </div>
    </section>

    <section id="counts-m-window">
      <h5><span class="sec-n">3</span>Which days?</h5>
      <p>
        In general, counts are conducted from <strong>18 July to 18 November</strong>, but counting
        often also takes place earlier or later.
      </p>
      <p>
        We keep this standard period and extend it to include 99% of the estimated passage, plus
        five days on either side. Added dates must have at least half their expected passage covered
        in <strong>one season in three</strong>, averaged over a week.
      </p>
      <figure class="figure w-100">
        <div
          ref="windowDiv"
          class="window-plot"
          role="img"
          :aria-label="`${name}: counting seasons and species records by calendar date, ${startYear}–${lastYear}`"
        ></div>
        <figcaption class="figure-caption">
          <strong>Figure 1.2.</strong> {{ startYear }}–{{ lastYear }}: seasons counted (light),
          seasons recording {{ name }} (dark), and coverage-adjusted mean birds per full day
          (seven-day moving average).
        </figcaption>
      </figure>
      <div class="callout callout-info">
        <strong>{{ name }}</strong
        >: {{ windowText }}. Across {{ startYear }}–{{ lastYear }},
        {{ outsideCount.toLocaleString() }} birds ({{ outsideShare }}%) were counted outside the
        standard period.<template v-if="beyond"> Passage also continues {{ beyond }}.</template>
      </div>
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
  surveyDays: { type: Object, required: true },
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
const beyond = computed(() =>
  props.data.window.beyond_counting
    .map((w) => ({ early: "before counting starts", late: "after counting ends" })[w] ?? w)
    .join(" and "),
);

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

const windowDiv = ref(null);
const windowVisible = usePlot(windowDiv);
const windowRows = computed(() => {
  const surveyed = new Set(
    props.surveyDays.date.filter(
      (date, i) =>
        Number(date.slice(0, 4)) >= startYear.value &&
        Number(date.slice(0, 4)) <= lastYear.value &&
        props.surveyDays.state[i] === "counted",
    ),
  );
  const recorded = new Set(
    props.data.days.date.filter((date, i) => surveyed.has(date) && props.data.days.count[i] > 0),
  );
  const counts = new Map();
  for (const date of surveyed) {
    const key = date.slice(5);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const species = new Map();
  for (const date of recorded) {
    const key = date.slice(5);
    species.set(key, (species.get(key) ?? 0) + 1);
  }
  const season = props.data.season;
  const rates = season.doy.map((_, i) => {
    const values = season.years
      .map((y, j) =>
        y >= startYear.value && y <= lastYear.value && season.c[j][i] >= 0.5
          ? (season.count[j][i] ?? 0) / season.c[j][i]
          : null,
      )
      .filter((v) => v != null);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });
  const mean = new Map(
    season.doy.map((doy, i) => {
      const values = rates.slice(Math.max(0, i - 3), i + 4).filter((v) => v != null);
      return [
        new Date(Date.UTC(2001, 0, doy)).toISOString().slice(5, 10),
        values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
      ];
    }),
  );
  const bounds = [...props.data.window.default, ...props.data.window.view].sort();
  const first = new Date(`2001-${bounds[0]}T00:00:00Z`);
  first.setUTCDate(first.getUTCDate() - 17);
  const end = new Date(`2001-${bounds.at(-1)}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() + 13);
  const rows = [];
  for (const d = new Date(first); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    const date = d.toISOString().slice(0, 10),
      key = date.slice(5);
    rows.push({
      date,
      counted: counts.get(key) ?? 0,
      recorded: species.get(key) ?? 0,
      mean: mean.get(key) ?? null,
    });
  }
  return rows;
});
const comparableCounts = computed(() =>
  props.data.days.date
    .map((date, i) => ({ date, count: props.data.days.count[i] ?? 0 }))
    .filter(
      (r) =>
        Number(r.date.slice(0, 4)) >= startYear.value &&
        Number(r.date.slice(0, 4)) <= lastYear.value,
    ),
);
const outsideCount = computed(() =>
  comparableCounts.value
    .filter(
      (r) =>
        r.date.slice(5) < props.data.window.default[0] ||
        r.date.slice(5) > props.data.window.default[1],
    )
    .reduce((sum, r) => sum + r.count, 0),
);
const outsideShare = computed(() => {
  const total = comparableCounts.value.reduce((sum, r) => sum + r.count, 0);
  return total ? ((100 * outsideCount.value) / total).toFixed(1) : "0";
});
function plotWindow() {
  if (!windowVisible.value) return;
  const rows = windowRows.value,
    x = rows.map((r) => r.date);
  plotReact(
    windowDiv.value,
    [
      {
        x: props.data.window.default.map((md) => `2001-${md}`),
        y: [1, 1],
        mode: "lines",
        line: { color: COLORS.historyInner, width: 10 },
        showlegend: false,
        hovertemplate: "Standard: %{x|%d %b}<extra></extra>",
      },
      {
        x: props.data.window.model.map((md) => `2001-${md}`),
        y: [0, 0],
        mode: "lines",
        line: { color: COLORS.accent, width: 10 },
        showlegend: false,
        hovertemplate: "Used here: %{x|%d %b}<extra></extra>",
      },
      {
        x,
        y: rows.map((r) => r.counted),
        yaxis: "y2",
        type: "bar",
        marker: { color: COLORS.historyOuter },
        name: "Seasons counted",
        hovertemplate: "%{x|%d %b}: %{y} seasons counted<extra></extra>",
      },
      {
        x,
        y: rows.map((r) => r.recorded),
        yaxis: "y2",
        type: "bar",
        width: 86400000 * 0.55,
        marker: { color: COLORS.counted },
        name: "Species recorded",
        hovertemplate: "%{x|%d %b}: %{y} seasons recording the species<extra></extra>",
      },
      {
        x,
        y: rows.map((r) => r.mean),
        yaxis: "y3",
        mode: "lines",
        line: { color: COLORS.counted, width: 2 },
        showlegend: false,
        hovertemplate:
          "%{x|%d %b}: %{y:,.1f} birds per full day (coverage-adjusted)<extra></extra>",
      },
    ],
    {
      margin: { t: 38, l: 70, r: 10, b: 35 },
      showlegend: true,
      legend: { orientation: "h", y: 1.16 },
      barmode: "overlay",
      bargap: 0.05,
      dragmode: false,
      xaxis: {
        type: "date",
        range: [x[0], x.at(-1)],
        anchor: "y3",
        tickformat: "%d %b",
        dtick: "M1",
        fixedrange: true,
      },
      yaxis: {
        domain: [0.88, 1],
        range: [-0.6, 1.6],
        tickvals: [1, 0],
        ticktext: ["Standard", "Used here"],
        showgrid: false,
        zeroline: false,
        fixedrange: true,
      },
      yaxis2: {
        domain: [0.5, 0.79],
        title: { text: "seasons" },
        rangemode: "tozero",
        fixedrange: true,
      },
      yaxis3: {
        domain: [0, 0.38],
        title: { text: "birds / full day" },
        rangemode: "tozero",
        fixedrange: true,
      },
      shapes: props.data.window.model.map((md) => ({
        type: "line",
        x0: `2001-${md}`,
        x1: `2001-${md}`,
        yref: "paper",
        y0: 0,
        y1: 0.84,
        line: { color: COLORS.accent, width: 1, dash: "dot" },
      })),
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(() => [windowVisible.value, props.data], plotWindow);

watch(() => [visible.value, props.effort, startYear.value], plotHistory);
</script>

<style scoped>
.window-plot {
  height: 440px;
}
</style>
