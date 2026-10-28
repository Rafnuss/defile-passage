<template>
  <div>
    <div ref="plotDiv" class="observed-day-plot"></div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { usePlot, plotReact } from "../../utils/usePlot";
import { clock, solarShift } from "../../services/explore";
import { COLORS, alpha } from "../../theme";
const props = defineProps({
  row: Object,
  predicted: Number,
  theta: Number,
  profile: Object,
  slots: Array,
});
const plotDiv = ref(null),
  visible = usePlot(plotDiv);
const dayProfile = computed(() => {
  const date = new Date(`${props.row.date}T12:00:00Z`);
  const doy = Math.floor((date - Date.UTC(date.getUTCFullYear(), 0, 1)) / 86400000) + 1;
  return props.profile.p[
    Math.max(0, Math.min(props.profile.p.length - 1, doy - props.profile.doy_start))
  ];
});
function plot() {
  if (!visible.value) return;
  const p = dayProfile.value,
    shift = solarShift(new Date(`${props.row.date}T12:00:00Z`));
  const slots = new Map(props.slots),
    x = p.map((_, i) => (i + 0.5) / props.profile.per_hour + shift);
  const updated =
    (props.theta + (props.row.conditioningC > 0 ? props.row.count : 0)) /
    (props.theta / props.predicted + props.row.conditioningC);
  const on = p.map((v, i) => (v > 0 ? i : -1)).filter((i) => i >= 0);
  const a = Math.floor(x[on[0]]),
    b = Math.ceil(x[on.at(-1)]);
  plotReact(
    plotDiv.value,
    [
      {
        x,
        y: p.map((v) => v * props.predicted),
        mode: "lines",
        name: "Daily prediction",
        line: { color: COLORS.faint, dash: "dot" },
        hoverinfo: "skip",
      },
      {
        x,
        y: p.map((v) => v * updated),
        mode: "lines",
        name: "Updated intensity",
        line: { color: COLORS.predicted, width: 2 },
        hoverinfo: "skip",
      },
      ...[true, false].map((counted) => ({
        x,
        y: p.map((v, i) => v * updated * (counted ? (slots.get(i) ?? 0) : 1 - (slots.get(i) ?? 0))),
        type: "bar",
        width: 1 / props.profile.per_hour,
        name: counted ? "Covered by counting" : "Uncounted",
        marker: {
          color: alpha(counted ? COLORS.counted : COLORS.predicted, 0.35),
          line: { width: 0 },
        },
        hovertemplate: "%{y:.1f} expected birds/hour<extra>%{fullData.name}</extra>",
      })),
    ],
    {
      barmode: "stack",
      margin: { t: 50, l: 50, r: 10, b: 35 },
      showlegend: true,
      legend: { orientation: "h", y: 1.2, font: { size: 10 } },
      xaxis: {
        range: [a, b],
        fixedrange: true,
        tickvals: Array.from({ length: b - a + 1 }, (_, i) => a + i).filter((h) => h % 2 === 0),
        ticktext: Array.from({ length: b - a + 1 }, (_, i) => a + i)
          .filter((h) => h % 2 === 0)
          .map((h) => clock(h)),
      },
      yaxis: { title: { text: "Expected birds/hour" }, rangemode: "tozero", fixedrange: true },
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(() => [visible.value, props.row, props.predicted, props.profile, props.slots], plot);
</script>

<style scoped>
.observed-day-plot {
  height: 360px;
  width: 100%;
}
</style>
