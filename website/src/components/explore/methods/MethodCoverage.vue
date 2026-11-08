<template>
  <section id="coverage">
    <h5><span class="sec-n">2</span>Counting effort: the coverage</h5>
    <p>
      Counting rarely covers the whole day, so the number of birds counted depends on when counting
      took place as well as on how many birds passed. The coverage&nbsp;<Tex e="c_d" /> accounts for
      this: it is the proportion of the day’s expected passage of the species that falls within the
      counting intervals. It is calculated before the model is fitted, in two steps: a time-of-day
      profile describes when in the day the species passes, and the coverage is the part of that
      profile covered by counting.
    </p>
    <p id="counts-m-resolution">
      The observed count <Tex e="N_d" /> is the number of birds recorded during the day’s counting
      intervals, each with a start and an end time. There is usually one interval per day, or
      several when counting was interrupted.
    </p>
    <p id="coverage-m-profile">
      Equal numbers of hours counted need not cover equal proportions of the day’s passage, because
      each species has a daily rhythm: raptors often pass later in the day than pigeons or finches.
      The <strong>time-of-day profile</strong>&nbsp;<Tex e="p_d(h)" /> is the expected proportion of
      the day’s birds passing per hour at time <Tex e="h" /> on date <Tex e="d" />. It is estimated
      from hourly counts. In full generality the profile could change with both the date and the
      year; we let it vary with the date but assume it is the same in every year.
    </p>
    <p id="coverage-m-coverage">
      The profile integrates to one over the full day. The <strong>coverage</strong>&nbsp;<Tex
        e="c_d"
      />
      is its integral over the counting intervals, so it lies between 0 (nothing counted) and 1 (the
      whole day’s passage counted):
    </p>
    <div class="eq">
      <Tex display e="c_d = \int_{\text{counting intervals}} p_d(h)\,\mathrm{d}h \tag{3}" />
    </div>
    <figure v-if="row" class="figure w-100">
      <div class="readout small mb-1">
        Counting from <strong>{{ clock(hFrom) }}</strong> to <strong>{{ clock(hTo) }}</strong>
        gives a coverage of
        <strong class="coverage-value"><Tex :e="`c_d = ${cov.toFixed(2)}`" /></strong>
        for {{ name }} on {{ rowDate }}.
      </div>
      <div ref="covDiv" class="plot-sm"></div>
      <!-- Two-handle slider on the plot's x axis: same range, inset by the plot's margins -->
      <div
        class="hours"
        :style="{
          marginLeft: `${COV_MARGIN.l - THUMB / 2}px`,
          marginRight: `${COV_MARGIN.r - THUMB / 2}px`,
        }"
      >
        <div class="hours-track"></div>
        <div class="hours-sel" :style="selStyle"></div>
        <input
          v-model.number="hFrom"
          type="range"
          :min="covAxis[0]"
          :max="covAxis[1]"
          :step="SLIDER_STEP"
          aria-label="Start of the count"
        />
        <input
          v-model.number="hTo"
          type="range"
          :min="covAxis[0]"
          :max="covAxis[1]"
          :step="SLIDER_STEP"
          aria-label="End of the count"
        />
      </div>
      <div class="text-center text-muted hours-hint">
        <i class="bi bi-arrows me-1"></i>drag the two handles to choose the time counted
      </div>
      <figcaption class="figure-caption">
        <strong>Figure 2.1.</strong> {{ name }}, {{ rowDate }}: the shaded share of the daily
        profile is the coverage of the selected counting interval.
      </figcaption>
    </figure>
    <p id="coverage-m-rate">
      The coverage links the expected full-day passage <Tex e="R_d" /> to the expected observed
      count, <Tex e="\mu_d = c_d R_d" /> (eq. 1). For example, if <Tex e="R_d=100" /> birds are
      expected over the day and counting covers <Tex e="c_d=0.6" /> of the day’s passage, the
      expected observed count is <Tex e="\mu_d=60" />. This is an average over days with the same
      conditions: the observed count <Tex e="N_d" /> on a particular day can be smaller or larger.
      Section 2.3 describes this variation.
    </p>
    <details id="coverage-m-solar" class="method-detail">
      <summary>Solar time, daylight and how the profile is fitted</summary>
      <p>
        The dataset stores hourly counts in local apparent solar time, with noon at the sun’s
        transit. This avoids the daylight-saving jump. The figure converts those hours to the local
        Europe/Paris clock.
      </p>
      <p>
        To account for shortening days, the profile is fitted over the fraction of daylight elapsed
        between civil dawn and dusk (sun 6° below the horizon), together with the calendar date. A
        small GAM smooths the relative hourly rates; the resulting curve is normalised to integrate
        to one.
      </p>
      <p>
        Days must have at least 90% of their birds timed, with at least two hours counted for half
        an hour or more. A species needs at least 500 timed birds for its own profile; otherwise it
        borrows its group’s profile, with a uniform daylight profile as the final fallback. This
        example uses {{ sourceLabel }}. The profile varies with date but is shared across years.
      </p>
    </details>
  </section>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS, alpha } from "../../../theme.js";
import { doyLabel, doyDate, solarShift, clock } from "../../../services/explore";
import Tex from "../Tex.vue";

const { locale } = useI18n();

const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});

const CONFIG = { displayModeBar: false, responsive: true };
// Figure 2.1's x axis (clock hours) and margins, shared by the plot and the hour slider below it
const COV_MARGIN = { t: 8, l: 48, r: 12, b: 28 };
const THUMB = 16; // px, the range thumb: its centre sits THUMB / 2 inside the input
const SLIDER_STEP = 0.25; // hours: the count's start and end move by a quarter of an hour

const lastYear = computed(() => props.data.trend?.last_year ?? new Date().getFullYear() - 1);

// The profile on the main passage's median date (profile.day): a continuous curve, the share of
// the day per hour at each slot of 1 / per_hour hours from solar hour `start`
const row = computed(() => props.data.profile?.day ?? null);
const shift = computed(() => (row.value ? solarShift(doyDate(row.value.doy, lastYear.value)) : 1));
// Clock hours from civil dawn to dusk on that day, rounded out to whole hours
const covAxis = computed(() => {
  const r = row.value;
  if (!r) return [4, 22];
  const t0 = r.start + shift.value;
  return [Math.floor(t0), Math.ceil(t0 + r.p.length / r.per_hour)];
});
const rowDate = computed(() => (row.value ? doyLabel(row.value.doy, locale.value) : ""));
const sourceLabel = computed(
  () =>
    ({ own: "its own profile", uniform: "uniform over daylight, too few birds timed to the hour" })[
      props.data.profile?.source
    ] ??
    `the profile of its group (${props.data.profile?.source}), too few birds timed to the hour`,
);

const hFrom = ref(8);
const hTo = ref(12);
watch(covAxis, ([a, b]) => {
  hFrom.value = Math.min(Math.max(hFrom.value, a), b - SLIDER_STEP);
  hTo.value = Math.max(Math.min(hTo.value, b), hFrom.value + SLIDER_STEP);
});
// Equation (1): the curve integrated over the time counted, slot by slot
const cov = computed(() => {
  const r = row.value;
  if (!r) return 0;
  const [a, b] = [hFrom.value - shift.value, hTo.value - shift.value];
  const w = 1 / r.per_hour;
  return r.p.reduce((s, x, k) => {
    const t0 = r.start + k * w;
    return s + x * Math.max(0, Math.min(b, t0 + w) - Math.max(a, t0));
  }, 0);
});
const selStyle = computed(() => {
  const f = (h) => (h - covAxis.value[0]) / (covAxis.value[1] - covAxis.value[0]);
  const pos = (h) => `calc(${THUMB / 2}px + ${f(h)} * (100% - ${THUMB}px))`;
  return {
    left: pos(hFrom.value),
    width: `calc(${f(hTo.value) - f(hFrom.value)} * (100% - ${THUMB}px))`,
  };
});

const covDiv = ref(null);
const covVisible = usePlot(covDiv);

function plotCoverage() {
  const r = row.value;
  if (!covVisible.value || !covDiv.value || !r) return;
  const s = shift.value;
  const w = 1 / r.per_hour;
  const x = r.p.map((_, k) => r.start + (k + 0.5) * w + s);
  const inside = x.map((t) => t > hFrom.value && t < hTo.value);
  const [a, b] = covAxis.value;
  const ticks = Array.from({ length: b - a + 1 }, (_, i) => a + i).filter((h) => h % 2 === 0);
  plotReact(
    covDiv.value,
    [
      {
        x,
        y: r.p,
        mode: "lines",
        fill: "tozeroy",
        line: { color: alpha(COLORS.faint, 0.9), width: 1.5 },
        fillcolor: alpha(COLORS.historyInner, 0.35),
        text: x.map((t) => clock(t, 5)),
        hovertemplate: "%{text}: %{y:.1%} of the day per hour<extra></extra>",
      },
      {
        x: x.map((t, k) => (inside[k] ? t : null)),
        y: r.p.map((p, k) => (inside[k] ? p : null)),
        mode: "lines",
        fill: "tozeroy",
        line: { color: COLORS.counted, width: 2 },
        fillcolor: alpha(COLORS.counted, 0.55),
        hoverinfo: "skip",
      },
    ],
    {
      margin: COV_MARGIN,
      dragmode: false,
      autosize: true,
      showlegend: false,
      font: { size: 11 },
      xaxis: {
        fixedrange: true,
        range: covAxis.value,
        tickvals: ticks,
        ticktext: ticks.map((h) => clock(h)),
      },
      yaxis: {
        title: { text: "Share of daily passage per hour" },
        tickformat: ".0%",
        fixedrange: true,
        rangemode: "tozero",
      },
    },
    CONFIG,
  );
}

// The handles never cross: at least a quarter of an hour counted
watch(hFrom, (h) => h >= hTo.value && (hFrom.value = hTo.value - SLIDER_STEP));
watch(hTo, (h) => h <= hFrom.value && (hTo.value = hFrom.value + SLIDER_STEP));
watch(() => [covVisible.value, row.value, hFrom.value, hTo.value], plotCoverage);
</script>

<style scoped>
.coverage-value {
  color: var(--dv-counted);
}
</style>
