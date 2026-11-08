<template>
  <figure class="figure w-100 conditional-example" :style="{ '--counted-color': COLORS.counted }">
    <div class="example-heading">
      <strong>{{ name }} · reconstruct a partly counted day</strong
      ><span>Fitted <Tex :e="`\\theta=${theta.toFixed(2)}`" /></span>
    </div>
    <div class="conditioning-controls">
      <label
        >Expected full-day passage <Tex e="R_d" />: <strong>{{ expected }}</strong>
        <input
          v-model.number="expected"
          aria-label="Example expected full-day passage"
          type="range"
          min="1"
          max="500"
          step="1"
          class="form-range"
        />
      </label>
      <label
        >Observed count <Tex e="N_d" />: <strong>{{ observed }}</strong>
        <input
          v-model.number="observed"
          aria-label="Example observed count"
          type="range"
          min="0"
          max="500"
          step="1"
          class="form-range"
        />
        <span class="control-note"
          ><strong>{{
            observed > coverage * expected
              ? "More"
              : observed < coverage * expected
                ? "Less"
                : "As expected"
          }}</strong
          ><template v-if="observed !== coverage * expected"> than expected</template> by the daily
          model.</span
        >
      </label>
      <label
        >Flocking <Tex e="\kappa" />:
        <strong>{{ flocking.toLocaleString("en", { maximumSignificantDigits: 3 }) }}</strong>
        <input
          v-model.number="logKappa"
          aria-label="Example flocking kappa"
          type="range"
          min="-2"
          max="4"
          step="0.01"
          class="form-range"
        />
        <span class="slider-endpoints"
          ><span>Stronger flocking</span><span>Nearly independent</span></span
        >
      </label>
    </div>
    <div class="profile-stage">
      <div ref="profileDiv" class="profile-plot"></div>
      <button
        type="button"
        class="btn btn-sm btn-outline-secondary simulate-button"
        @click="realisation++"
      >
        Draw another possible day
      </button>
    </div>
    <div
      class="hours"
      :style="{
        marginLeft: `${PROFILE_MARGIN.l - THUMB / 2}px`,
        marginRight: `${PROFILE_MARGIN.r - THUMB / 2}px`,
      }"
    >
      <div class="hours-track"></div>
      <div class="hours-sel" :style="selStyle"></div>
      <input
        v-model.number="start"
        type="range"
        :min="axis[0]"
        :max="axis[1]"
        step="0.25"
        aria-label="Example counting start"
      />
      <input
        v-model.number="end"
        type="range"
        :min="axis[0]"
        :max="axis[1]"
        step="0.25"
        aria-label="Example counting end"
      />
    </div>
    <div class="text-center text-muted hours-hint">
      <i class="bi bi-arrows me-1"></i>drag the two handles to choose the time counted · Coverage
      <Tex :e="`c_d=${coverage.toFixed(2)}`" />
    </div>
    <div class="conditioning-visual" aria-live="polite">
      <p class="small">Keep the counted birds; estimate only the missing part:</p>
      <div v-for="row in totals" :key="row.label" class="conditioning-row">
        <span>{{ row.label }} <Tex v-if="row.tex" :e="row.tex" /></span>
        <div class="conditioning-total">
          <div class="conditioning-track total-track">
            <span
              :style="{ width: `${(100 * observed) / totalMax}%`, background: COLORS.counted }"
            ></span>
            <span
              :style="{ width: `${(100 * row.missing) / totalMax}%`, background: row.color }"
            ></span>
          </div>
          <span
            v-if="row.interval"
            class="conditioning-interval"
            :style="{
              left: `${(100 * row.interval[0]) / totalMax}%`,
              width: `${(100 * (row.interval[1] - row.interval[0])) / totalMax}%`,
            }"
          ></span>
        </div>
        <strong>{{ Math.round(observed + row.missing) }}</strong>
      </div>
      <div class="conditioning-legend" aria-label="Legend">
        <span
          ><i :style="{ background: COLORS.counted }"></i>Counted <Tex :e="`N_d=${observed}`"
        /></span>
        <span
          ><i :style="{ background: COLORS.predicted }"></i>Estimated missing
          <Tex :e="`\\widehat M_d=${Math.round(missing)}`"
        /></span>
        <span
          ><i class="legend-interval"></i>80% interval for <Tex e="F_d" />: {{ predictive[0] }}–{{
            predictive[1]
          }}</span
        >
      </div>
    </div>
    <figcaption class="figure-caption">
      <strong>Figure 3.1.</strong> {{ name }}, {{ doyLabel(profile.doy, "en") }}. The observed count
      <Tex e="N_d" /> is your input and stays fixed. Each dot is one bird in a possible full day
      conditional on that count: rust birds are allocated within the counting interval, blue birds
      are drawn for the missing hours. Counted birds’ times are illustrative. The dotted curve is
      the daily-model prediction; the solid curve is the updated expectation. The button redraws a
      possible day without changing your inputs or the mean estimate.
    </figcaption>
  </figure>
</template>
<script setup>
import { ref, computed, watch } from "vue";
import Tex from "./Tex.vue";
import { COLORS, alpha } from "../../theme.js";
import { gammaSampler } from "../../utils/simulation";
import { usePlot, plotReact } from "../../utils/usePlot";
import { clock, doyLabel, doyDate, solarShift } from "../../services/explore";
const props = defineProps({
  theta: { type: Number, required: true },
  kappa: { type: Number, required: true },
  name: { type: String, required: true },
  profile: { type: Object, required: true },
  year: { type: Number, required: true },
});
const logKappa = ref(Math.log10(props.kappa));
watch(
  () => props.kappa,
  (value) => {
    logKappa.value = Math.log10(value);
  },
);
const flocking = computed(() => 10 ** logKappa.value);
const expected = ref(100),
  observed = ref(30),
  start = ref(9),
  end = ref(14);
const shift = computed(() => solarShift(doyDate(props.profile.doy, props.year)));
const bounds = computed(() => [
  props.profile.start + shift.value,
  props.profile.start + shift.value + props.profile.p.length / props.profile.per_hour,
]);
const axis = computed(() => [Math.floor(bounds.value[0]), Math.ceil(bounds.value[1])]);
const PROFILE_MARGIN = { t: 44, l: 50, r: 12, b: 40 },
  THUMB = 16;
const selStyle = computed(() => {
  const f = (h) => (h - axis.value[0]) / (axis.value[1] - axis.value[0]);
  return {
    left: `calc(${THUMB / 2}px + ${f(start.value)} * (100% - ${THUMB}px))`,
    width: `calc(${f(end.value) - f(start.value)} * (100% - ${THUMB}px))`,
  };
});
watch(
  axis,
  ([a, b]) => {
    start.value = Math.max(a, Math.min(start.value, b - 0.25));
    end.value = Math.min(b, Math.max(end.value, start.value + 0.25));
  },
  { immediate: true },
);
watch(start, (h) => {
  start.value = Math.max(Math.ceil(bounds.value[0] * 4) / 4, Math.min(h, end.value - 0.25));
});
watch(end, (h) => {
  end.value = Math.min(Math.floor(bounds.value[1] * 4) / 4, Math.max(h, start.value + 0.25));
});
const coverage = computed(() =>
  props.profile.p.reduce((sum, p, i) => {
    const a = bounds.value[0] + i / props.profile.per_hour;
    return (
      sum +
      p *
        Math.max(0, Math.min(end.value, a + 1 / props.profile.per_hour) - Math.max(start.value, a))
    );
  }, 0),
);
const updated = computed(
  () => (props.theta + observed.value) / (props.theta / expected.value + coverage.value),
);
const missing = computed(() => (1 - coverage.value) * updated.value);
// Fixed seed keeps slider comparisons reproducible. Gamma draws match fill_draws;
// Poisson draws use independent chunks to keep the exact sampler stable at large means.
const predictive = computed(() => {
  const { gamma, poisson } = gammaSampler(73491);
  const draws = Array.from({ length: 2000 }, () => {
    if (coverage.value === 1) return observed.value;
    const intensity =
      gamma(props.theta + observed.value) / (props.theta / expected.value + coverage.value);
    const mean = (gamma(flocking.value * (1 - coverage.value)) * intensity) / flocking.value;
    return observed.value + poisson(mean);
  }).sort((a, b) => a - b);
  return [draws[199], draws[1799]];
});
const totals = computed(() => [
  {
    label: "Simulated total",
    tex: "F_d",
    missing: simulation.value.birds.length - observed.value,
    color: alpha(COLORS.predicted, 0.7),
  },
  {
    label: "Simple completion",
    tex: "\\widehat F_d^{\\mathrm{simple}}",
    missing: (1 - coverage.value) * expected.value,
    color: alpha(COLORS.predicted, 0.4),
  },
  {
    label: "Updated completion",
    tex: "\\widehat F_d",
    interval: predictive.value,
    missing: missing.value,
    color: COLORS.predicted,
  },
]);
const totalMax = computed(() =>
  Math.max(1, ...totals.value.map((row) => observed.value + row.missing), predictive.value[1]),
);
const realisation = ref(0);
// Keep the supplied count fixed. Draw missing passage from the production Gamma–Poisson
// update plus flocking increments; allocate the known birds only to illustrate their times.
const simulation = computed(() => {
  const seed = (4183 + Math.imul(realisation.value, 2654435761)) >>> 0;
  const { gamma } = gammaSampler(seed);
  const intensity =
    gamma(props.theta + observed.value) / (props.theta / expected.value + coverage.value);
  const slots = props.profile.p.map((p, i) => {
    const a = bounds.value[0] + i / props.profile.per_hour,
      b = a + 1 / props.profile.per_hour;
    return { p, a, b, from: Math.max(a, start.value), to: Math.min(b, end.value) };
  });
  const countedSlots = slots.filter((s) => s.p > 0 && s.to > s.from);
  const { uniform, logGamma } = gammaSampler(seed ^ 17389);
  const logs = countedSlots.map((s) => logGamma(flocking.value * s.p * (s.to - s.from)));
  const maximum = Math.max(...logs),
    mass = logs.map((v) => Math.exp(v - maximum));
  const total = mass.reduce((a, b) => a + b, 0);
  const cumulative = mass.map((_, i) => mass.slice(0, i + 1).reduce((a, b) => a + b, 0) / total);
  const counted = Array.from({ length: observed.value }, () => {
    const u = uniform(),
      slot = countedSlots[cumulative.findIndex((v) => v >= u)];
    return { hour: slot.from + uniform() * (slot.to - slot.from), height: 0.3 + 0.6 * uniform() };
  });
  const missed = slots.flatMap((s, i) =>
    [
      [s.a, Math.min(s.b, start.value)],
      [Math.max(s.a, end.value), s.b],
    ].flatMap(([a, b], part) => {
      if (b <= a || s.p === 0) return [];
      // Separate streams stop changes in the daily prediction reshuffling existing bird times.
      const rates = gammaSampler(seed ^ Math.imul(i * 2 + part + 1, 1597334677));
      const positions = gammaSampler(seed ^ Math.imul(i * 2 + part + 1, 3812015801));
      const mean = (rates.gamma(flocking.value * s.p * (b - a)) * intensity) / flocking.value;
      let elapsed = 0;
      const birds = [];
      for (;;) {
        elapsed -= Math.log(rates.uniform());
        if (elapsed >= mean) break;
        birds.push({
          hour: a + positions.uniform() * (b - a),
          height: 0.3 + 0.6 * positions.uniform(),
        });
      }
      return birds;
    }),
  );
  return { intensity, birds: [...counted, ...missed] };
});
const profileDiv = ref(null),
  visible = usePlot(profileDiv);
function plotProfile() {
  if (!visible.value) return;
  // Include the interval boundaries so the coloured areas meet the handles exactly.
  const x = [
    ...new Set([
      bounds.value[0],
      Math.max(bounds.value[0], Math.min(start.value, bounds.value[1])),
      Math.max(bounds.value[0], Math.min(end.value, bounds.value[1])),
      bounds.value[1],
      ...props.profile.p.map((_, i) => bounds.value[0] + (i + 0.5) / props.profile.per_hour),
    ]),
  ].sort((a, b) => a - b);
  const p = x.map(
    (h) =>
      props.profile.p[
        Math.min(
          props.profile.p.length - 1,
          Math.floor((h - bounds.value[0]) * props.profile.per_hour),
        )
      ],
  );
  plotReact(
    profileDiv.value,
    [
      {
        x,
        y: p.map((v) => v * expected.value),
        mode: "lines",
        name: "Daily-model prediction",
        line: { color: COLORS.faint, dash: "dot", width: 2 },
        hovertemplate: "%{y:.1f} birds/hour<extra>Daily model</extra>",
      },
      ...[
        [bounds.value[0], start.value, COLORS.predicted, "Estimated outside counting"],
        [start.value, end.value, COLORS.counted, "Counted interval"],
        [end.value, bounds.value[1], COLORS.predicted, "Estimated outside counting"],
      ].map(([a, b, color, name], i) => ({
        x: x.filter((h) => h >= a && h <= b),
        y: p.filter((_, j) => x[j] >= a && x[j] <= b).map((v) => v * updated.value),
        mode: "lines",
        fill: "tozeroy",
        fillcolor: alpha(color, 0.25),
        line: { color, width: 2 },
        name,
        showlegend: i !== 2,
        hovertemplate: "%{y:.1f} birds/hour<extra>Updated expectation</extra>",
      })),
      ...[true, false].flatMap((counted) => {
        const birds = simulation.value.birds.filter(
          (bird) => (bird.hour >= start.value && bird.hour < end.value) === counted,
        );
        const color = counted ? COLORS.counted : COLORS.predicted;
        return [
          {
            x: birds.flatMap((r) => [r.hour, r.hour, null]),
            y: birds.flatMap((r) => [0, r.height, null]),
            yaxis: "y2",
            mode: "lines",
            line: { color, width: 1 },
            showlegend: false,
            hoverinfo: "skip",
          },
          {
            x: birds.map((r) => r.hour),
            y: birds.map((r) => r.height),
            yaxis: "y2",
            mode: "markers",
            marker: { size: 3, color },
            showlegend: false,
            hovertemplate: counted
              ? "One counted bird<extra></extra>"
              : "One missed bird<extra></extra>",
          },
        ];
      }),
    ],
    {
      margin: PROFILE_MARGIN,
      showlegend: true,
      legend: {
        orientation: "h",
        x: 0.5,
        xanchor: "center",
        y: 1.03,
        yanchor: "bottom",
        font: { size: 10 },
      },
      xaxis: {
        anchor: "y2",
        title: { text: "Local clock time" },
        fixedrange: true,
        range: axis.value,
        tickvals: Array.from({ length: 25 }, (_, i) => i).filter((i) => i % 2 === 0),
        ticktext: Array.from({ length: 13 }, (_, i) => clock(i * 2)),
      },
      yaxis: {
        title: { text: "Expected birds per hour" },
        fixedrange: true,
        rangemode: "tozero",
        domain: [0.24, 1],
      },
      yaxis2: {
        title: { text: "Birds", font: { size: 10 } },
        domain: [0, 0.14],
        range: [0, 1],
        fixedrange: true,
        showgrid: false,
        showticklabels: false,
        zeroline: false,
      },
      shapes: [start.value, end.value].map((h) => ({
        type: "line",
        x0: h,
        x1: h,
        yref: "paper",
        y0: 0,
        y1: 1,
        line: { color: COLORS.counted, width: 1, dash: "dot" },
      })),
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(
  () => [
    visible.value,
    props.profile,
    start.value,
    end.value,
    expected.value,
    observed.value,
    props.theta,
    simulation.value.birds,
  ],
  plotProfile,
);
</script>

<style scoped>
.profile-stage {
  position: relative;
}
.simulate-button {
  position: absolute;
  right: 12px;
  bottom: 5px;
  font-size: 0.7rem;
  padding: 2px 6px;
}
.example-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}
.example-heading span {
  font-size: 0.85rem;
}
.control-note {
  display: block;
  font-size: 0.72rem;
  line-height: 1.4;
  color: var(--dv-muted);
}
.slider-endpoints {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: var(--dv-muted);
}
.conditional-example .hours input::-webkit-slider-thumb {
  background: var(--counted-color);
  box-shadow: 0 0 0 1px var(--counted-color);
}
.conditional-example .hours input::-moz-range-thumb {
  background: var(--counted-color);
  box-shadow: 0 0 0 1px var(--counted-color);
}
.conditional-example .hours .hours-sel {
  background: var(--counted-color);
}
.conditioning-controls {
  padding: 0.4rem 0.8rem;
  background: var(--dv-bg);
  border-radius: 6px;
  margin-bottom: 0;
}
.conditioning-controls {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.profile-plot {
  height: 400px;
  width: 100%;
}
.conditioning-visual {
  margin: 1rem 0;
}
.conditioning-track {
  height: 14px;
  background: var(--bs-border-color, #e1ddd3);
  border-radius: 3px;
  overflow: hidden;
}
.conditioning-track span {
  display: block;
  height: 100%;
}
.conditioning-row {
  display: grid;
  grid-template-columns: minmax(125px, 1fr) 2fr 55px;
  align-items: center;
  gap: 10px;
  margin: 0.6rem 0;
  font-size: 0.85rem;
}
.conditioning-row strong {
  text-align: right;
}
.conditioning-total {
  position: relative;
}
.conditioning-interval {
  position: absolute;
  top: 6px;
  height: 2px;
  background: #24211d;
  border-left: 1px solid #24211d;
  border-right: 1px solid #24211d;
}
.conditioning-legend {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  width: 100%;
  font-size: 0.8rem;
  margin: 0.8rem 0;
}
.conditioning-legend span {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.conditioning-legend i {
  display: inline-block;
  width: 20px;
  height: 10px;
}
.conditioning-legend .legend-interval {
  height: 2px;
  background: #24211d;
}
.total-track {
  display: flex;
}
@media (max-width: 500px) {
  .simulate-button {
    position: static;
    display: block;
    margin: 0 0 0.5rem auto;
  }
  .conditioning-legend {
    grid-template-columns: 1fr;
  }
  .conditioning-controls {
    grid-template-columns: 1fr;
  }
  .conditioning-row {
    grid-template-columns: 1fr 55px;
  }
  .conditioning-row > span {
    grid-column: 1 / -1;
  }
}
</style>
