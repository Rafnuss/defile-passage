<template>
  <div
    ref="plotDiv"
    class="passage-trend-plot"
    role="img"
    aria-label="Annual 10%, 50% and 90% passage dates with 80% reconstruction intervals; linear trends with 95% uncertainty bands"
  ></div>
</template>
<script setup>
import { ref, watch } from "vue";
import { PASSAGE_COLORS, alpha } from "../../theme";
import { doyLabel } from "../../services/explore";
import { plotReact, usePlot } from "../../utils/usePlot";
const props = defineProps({
  records: { type: Array, required: true },
  trends: { type: Object, default: () => ({}) },
});
const plotDiv = ref(null),
  visible = usePlot(plotDiv);
function plot() {
  if (!visible.value) return;
  const traces = [],
    dates = [];
  [10, 50, 90].forEach((q, j) => {
    const f = props.trends[`q${q}`],
      color = PASSAGE_COLORS[j];
    const p = props.records.filter((r) => r[`q${q}`] != null);
    const x = f?.year ?? p.map((r) => r.year);
    const y = f?.annual ?? p.map((r) => r[`q${q}`]);
    dates.push(...y, ...(f?.lo ?? []), ...(f?.hi ?? []));
    if (f)
      traces.push(
        {
          x,
          y: f.lo,
          mode: "lines",
          line: { width: 0 },
          hoverinfo: "skip",
          showlegend: false,
          legendgroup: String(q),
        },
        {
          x,
          y: f.hi,
          mode: "lines",
          line: { width: 0 },
          legendgroup: String(q),
          fill: "tonexty",
          fillcolor: alpha(color, 0.12),
          hoverinfo: "skip",
          showlegend: false,
        },
        {
          x,
          y: f.date,
          mode: "lines",
          line: { color, width: 2 },
          legendgroup: String(q),
          showlegend: false,
          hoverinfo: "skip",
        },
      );
    traces.push({
      x,
      y,
      mode: "markers",
      marker: { color, size: 5 },
      legendgroup: String(q),
      name: `${q}%${f ? ` · ${(f.slope * 10).toFixed(1)} days/decade` : ""}`,
      error_y: f
        ? {
            type: "data",
            symmetric: false,
            array: f.annual_hi.map((v, i) => v - y[i]),
            arrayminus: f.annual_lo.map((v, i) => y[i] - v),
            color: alpha(color, 0.5),
            width: 0,
          }
        : undefined,
      text: y.map((d) => doyLabel(d, "en")),
      hovertemplate: `%{x}: %{text}<extra>${q}% passage${f ? `<br>Trend: ${(f.slope * 10).toFixed(1)} days/decade<br>95% interval ${(f.slope_lo * 10).toFixed(1)}–${(f.slope_hi * 10).toFixed(1)}` : ""}</extra>`,
    });
  });
  const first = Math.floor(Math.min(...dates) / 14) * 14;
  const ticks = Array.from(
    { length: Math.ceil((Math.max(...dates) - first) / 14) + 1 },
    (_, i) => first + 14 * i,
  );
  plotReact(
    plotDiv.value,
    traces,
    {
      margin: { t: plotDiv.value.clientWidth < 500 ? 95 : 55, l: 65, r: 15, b: 40 },
      showlegend: true,
      legend: { orientation: "h", x: 0.5, xanchor: "center", y: 1.15, font: { size: 11 } },
      xaxis: { fixedrange: true, title: { text: "Year" } },
      yaxis: {
        fixedrange: true,
        title: { text: "Passage date" },
        tickvals: ticks,
        ticktext: ticks.map((d) => doyLabel(d, "en")),
      },
    },
    { displayModeBar: false, responsive: true },
  );
}
watch(() => [visible.value, props.records, props.trends], plot);
</script>
<style scoped>
.passage-trend-plot {
  height: 440px;
  width: 100%;
}
</style>
