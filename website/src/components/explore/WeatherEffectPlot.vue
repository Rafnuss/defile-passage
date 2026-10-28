<template>
  <div class="weather-effect">
    <h6>{{ spec.title }}</h6>
    <svg
      v-if="effect.rose"
      class="wind-rose"
      viewBox="0 0 300 290"
      role="img"
      :aria-label="`Passage multiplier for winds from each direction at ${effect.speed} m/s, compared with calm`"
    >
      <g v-for="(row, i) in effect.rose" :key="row.from">
        <line
          x1="150"
          y1="138"
          :x2="point(roseMax, i).x"
          :y2="point(roseMax, i).y"
          stroke="var(--dv-grid)"
        />
        <text
          :x="150 + 126 * Math.sin((i * Math.PI) / 4)"
          :y="142 - 126 * Math.cos((i * Math.PI) / 4)"
          text-anchor="middle"
          class="rose-label"
        >
          {{ row.from }}
        </text>
      </g>
      <circle
        cx="150"
        cy="138"
        :r="radius(1)"
        fill="none"
        stroke="var(--dv-faint)"
        stroke-dasharray="3 3"
      />
      <polygon
        :points="rosePolygon"
        :fill="alpha(COLORS.teal, 0.15)"
        stroke="var(--dv-teal)"
        stroke-width="2"
      />
      <g v-for="(row, i) in effect.rose" :key="`interval-${row.from}`">
        <title>
          {{ row.from }}: ×{{ row.effect.toFixed(2) }} (95% {{ row.lo.toFixed(2) }}–{{
            row.hi.toFixed(2)
          }})
        </title>
        <line
          :x1="point(row.lo, i).x"
          :y1="point(row.lo, i).y"
          :x2="point(row.hi, i).x"
          :y2="point(row.hi, i).y"
          stroke="var(--dv-teal)"
          stroke-width="3"
        />
        <circle
          :cx="point(row.effect, i).x"
          :cy="point(row.effect, i).y"
          r="3"
          fill="var(--dv-teal)"
        />
      </g>
      <circle cx="150" cy="138" r="2" fill="var(--dv-faint)" />
      <text x="150" y="280" text-anchor="middle" class="rose-label">
        {{ effect.speed }} m/s · dashed circle = ×1 (calm)
      </text>
    </svg>
    <div
      v-else
      ref="plotDiv"
      class="weather-effect-plot"
      role="img"
      :aria-label="`${spec.title}: fitted passage multiplier and 95% interval`"
    ></div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { usePlot, plotReact } from "../../utils/usePlot";
import { COLORS, alpha } from "../../theme.js";
const props = defineProps({ effect: { type: Object, required: true } });
const SPECS = {
  rain: { title: "Precipitation", label: "mm/hour vs dry", lo: 0, hi: 1, log: true },
  rain_yesterday: {
    title: "Previous-day precipitation",
    label: "mm/hour vs dry yesterday",
    lo: 0,
    hi: 1,
    log: true,
  },
  sunshine: { title: "Sunshine", label: "sunshine fraction vs overcast", lo: 0, hi: 1 },
  boundary_layer: { title: "Thermal mixing", label: "change in mixing depth (km)", lo: 0, hi: 1 },
  pressure_change: {
    title: "Pressure change",
    label: "24-hour pressure change (hPa)",
    lo: -5,
    hi: 5,
  },
  temperature_anomaly: {
    title: "Temperature anomaly",
    label: "change from usual (°C)",
    lo: -3,
    hi: 3,
  },
};
const spec = computed(
  () =>
    SPECS[props.effect.term] ?? {
      title: "Wind from each direction",
      label: `direction at ${props.effect.speed} m/s, vs calm`,
    },
);
const roseMax = computed(() => Math.max(1, ...(props.effect.rose ?? []).map((r) => r.hi)));
const radius = (value) => (108 * value) / roseMax.value;
const point = (value, i) => ({
  x: 150 + radius(value) * Math.sin((i * Math.PI) / 4),
  y: 138 - radius(value) * Math.cos((i * Math.PI) / 4),
});
const rosePolygon = computed(() =>
  (props.effect.rose ?? [])
    .map((r, i) => {
      const p = point(r.effect, i);
      return `${p.x},${p.y}`;
    })
    .join(" "),
);
const plotDiv = ref(null);
const visible = usePlot(plotDiv);
function plot() {
  if (!visible.value) return;
  const e = props.effect,
    s = spec.value;
  const x = Array.from({ length: 41 }, (_, i) => s.lo + ((s.hi - s.lo) * i) / 40);
  const multiplier = (bound, v) =>
    Math.exp((Math.log(bound) * (s.log ? Math.log1p(v) : v)) / e.contrast);
  const low = x.map((v) => Math.min(multiplier(e.lo, v), multiplier(e.hi, v)));
  const high = x.map((v) => Math.max(multiplier(e.lo, v), multiplier(e.hi, v)));
  const traces = [
    {
      x: [...x, ...x.slice().reverse()],
      y: [...high, ...low.slice().reverse()],
      fill: "toself",
      fillcolor: alpha(COLORS.teal, 0.15),
      line: { width: 0 },
      mode: "lines",
      hoverinfo: "skip",
    },
    {
      x,
      y: x.map((v) => multiplier(e.effect, v)),
      mode: "lines",
      line: { color: COLORS.teal, width: 2 },
      hovertemplate: "%{x:.2f}: ×%{y:.2f}<extra></extra>",
    },
  ];
  plotReact(
    plotDiv.value,
    traces,
    {
      margin: { t: 5, l: 43, r: 10, b: 47 },
      showlegend: false,
      xaxis: {
        fixedrange: true,
        title: { text: s.label, font: { size: 10 } },
        tickfont: { size: 10 },
      },
      yaxis: {
        fixedrange: true,
        title: { text: "× passage", font: { size: 10 } },
        tickfont: { size: 10 },
        type: "log",
        tickvals: [0.1, 0.25, 0.5, 1, 2, 4, 10],
      },
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: 1,
          y1: 1,
          line: { color: COLORS.faint, width: 1, dash: "dot" },
        },
      ],
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(() => [visible.value, props.effect], plot);
</script>
