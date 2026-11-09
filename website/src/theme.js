// The site's palette, taken from the Défilé logo (kite rust, golden grass, olive trees, slate
// mountains, charcoal ink on cream) and shared by the charts (here) and the page
// (src/theme.css, same values). Each data colour has one meaning everywhere: slate-blue is the
// model (forecast, estimate), rust is what was counted, warm grey bands with an ink median are past
// years.

export const COLORS = {
  // Neutrals: the logo's charcoal ink lines on cream paper
  ink: "#24211d",
  muted: "#625c53",
  faint: "#948d82",
  line: "#e0dacd",
  grid: "#ece7dc",
  paper: "#faf8f2",
  surface: "#ffffff",

  // Interface accent (links, active tab, focus): the olive of the trees
  accent: "#5a6b23",

  // Data
  predicted: "#3d6a8f", // model: forecast, estimated totals, smooth trends (slate-blue mountains)
  counted: "#c0562a", // observed: Trektellen counts (the kite's rust)
  historyOuter: "#e3ded2", // past years, wide band (e.g. 5–95%)
  historyInner: "#bdb6a7", // past years, central band (e.g. 20–80%)
  median: "#24211d", // past years' median

  // Secondary categories
  gold: "#d9a92e", // highlights, caveats (the sunlit grass)
  ochre: "#c4801c", // age (the kite's tail)
  plum: "#7a4f7f", // sex, demography
  sage: "#6f8a3a", // model fit, increase
  red: "#a83a24", // decrease, warnings
  pink: "#c2477d", // the day's weather (the trend model's weather term): a colour everyone can name

  // Sequential slate-blues, light to dark, for ordered classes (e.g. ≥1, ≥10, ≥100, ≥1000 birds)
  blues: ["#b3c7d8", "#7a9cb9", "#3d6a8f", "#1f3c56"],
};

/** A colour of the palette (hex) with an alpha, as rgba() for Plotly fills. */
export function alpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

export const FONT_FAMILY =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

const axis = {
  gridcolor: COLORS.grid,
  linecolor: COLORS.line,
  zerolinecolor: COLORS.line,
  tickcolor: COLORS.line,
  tickfont: { color: COLORS.muted },
  title: { font: { color: COLORS.muted, size: 12 } },
};

/** Plotly template: fonts, axes, hover labels and default trace colours of every chart. */
export const PLOT_TEMPLATE = {
  layout: {
    font: { family: FONT_FAMILY, size: 12, color: COLORS.ink },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    colorway: [COLORS.predicted, COLORS.counted, COLORS.ochre, COLORS.sage, COLORS.plum],
    xaxis: axis,
    yaxis: axis,
    hoverlabel: {
      bgcolor: COLORS.surface,
      bordercolor: COLORS.line,
      font: { family: FONT_FAMILY, size: 12, color: COLORS.ink },
    },
    legend: { font: { color: COLORS.muted } },
  },
};

// Components retain their colour in equations, labels and figures. Rust is reserved for counts.
export const MODEL_COLORS = {
  trend: COLORS.predicted,
  year: "#92734e",
  season: COLORS.sage,
  shift: COLORS.plum,
  episode: COLORS.ochre,
  weather: COLORS.pink,
};
export const PASSAGE_COLORS = [COLORS.sage, COLORS.plum, COLORS.ochre];
