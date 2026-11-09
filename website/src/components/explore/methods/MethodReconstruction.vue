<template>
  <div>
    <section id="model-m-fill">
      <h5><span class="sec-n">1</span>Three cases for reconstructing a full day</h5>
      <p>
        The model of <a href="#model">chapter 2</a> gives the <em>expected</em> full-day passage
        <Tex e="R_d" />: the average over days like this one, with the same date, year and weather.
        What we want here is the number of birds that actually passed on that day, the full-day
        total <Tex e="F_d" />: the birds counted plus those missed. To estimate <Tex e="F_d" />, we
        distinguish three cases based on the original daily coverage <Tex e="c_d" />:
      </p>
      <p v-if="!data.trend" class="callout callout-info">
        {{ name }} has no fitted daily count model. Choose a species with a fitted model to inspect
        reconstruction.
      </p>
      <div v-if="data.trend" class="table-responsive">
        <table class="table table-sm small">
          <thead>
            <tr>
              <th>Case</th>
              <th>Counting coverage</th>
              <th>How the full day is reconstructed</th>
              <th v-if="cases">Share of model days</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td>Uncounted or too short, <Tex :e="`c_d&lt;${data.trend?.min_coverage}`" /></td>
              <td>
                Predict from the expected full-day passage <Tex e="R_d" />. Birds recorded in a
                count this short are kept and added to the prediction; they do not update it.
              </td>
              <td v-if="cases">{{ cases.none }}%</td>
            </tr>
            <tr>
              <td>2</td>
              <td>Fully counted, <Tex e="c_d=1" /></td>
              <td>Keep the observed count: <Tex e="F_d=N_d" />.</td>
              <td v-if="cases">{{ cases.full }}%</td>
            </tr>
            <tr>
              <td>3</td>
              <td>Partly counted, <Tex :e="`${data.trend?.min_coverage}\\le c_d&lt;1`" /></td>
              <td>See the <a href="#reconstruction-m-condition">within-day model below</a>.</td>
              <td v-if="cases">{{ cases.partial }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="data.trend">
        For an uncounted day (case 1), we predict the expected full-day passage <Tex e="R_d" /> from
        the model of <a href="#model">chapter 2</a>, using its date, year, weather and surrounding
        episode. We draw 1 000 possible totals around this expectation. For a partly counted day
        (case 3), the observed birds provide extra information, as explained next.
      </p>
    </section>
    <section v-if="data.trend" id="reconstruction-m-condition">
      <h5><span class="sec-n">2</span>A within-day model for missing passage</h5>
      <h6>Start with the expected full-day passage</h6>
      <p>
        For a partly counted day (case 3), the full-day total <Tex e="F_d" /> is the observed count
        <Tex e="N_d" /> plus the missing birds <Tex e="M_d" />:
      </p>
      <div class="eq"><Tex display e="F_d=N_d+M_d" /></div>
      <p>
        A simple estimate of the missing birds multiplies the expected full-day passage
        <Tex e="R_d" /> by the missing share <Tex e="1-c_d" />:
      </p>
      <div class="eq"><Tex display e="\widehat M_d^{\mathrm{simple}}=(1-c_d)R_d" /></div>
      <p>
        However, this ignores what the observed hours tell us about this particular day. Passage is
        often above or below its expected full-day passage across several hours: a busy morning can
        signal a busy afternoon. Using the same prediction for both busy and quiet observed days can
        therefore overestimate or underestimate the birds missed.
      </p>
      <h6>Use the counted hours to update the intensity</h6>
      <p>
        To use what the counted hours say about this particular day, we write the negative binomial
        of <a href="#model-m-scatter">section 2.2</a> in its two equivalent parts: the
        <strong>intensity</strong> <Tex e="\lambda_d" />, how busy this day is, and the Poisson
        count given that intensity. Written so, the observed count updates the intensity, and the
        updated intensity predicts the uncounted hours. This is a
        <strong>Gamma–Poisson model</strong>. The intensity <Tex e="\lambda_d" /> has a Gamma
        distribution with mean <Tex e="R_d" /> and shape <Tex e="\theta" />, the same dispersion
        parameter fitted above. We write Gamma distributions using shape and rate, so their mean is
        shape divided by rate. Given that intensity, the observed count <Tex e="N_d" /> is Poisson
        with mean <Tex e="c_d\lambda_d" />:
      </p>
      <div class="eq">
        <Tex
          display
          e="\lambda_d\mid R_d,\theta\sim\mathrm{Gamma}(\theta,\theta/R_d),\qquad N_d\mid\lambda_d,c_d\sim\mathrm{Poisson}(c_d\lambda_d)"
        />
      </div>
      <p>
        The key idea is to use the intensity learned from counted hours to predict passage in
        uncounted hours. We update our knowledge of the <em>same</em> <Tex e="\lambda_d" /> by
        multiplying its initial Gamma density by the Poisson likelihood of the observed count
        <Tex e="N_d" />, then normalising the result to a probability distribution. This is Bayes’
        rule; the intensity itself is not multiplied by the count. A Gamma density times this
        Poisson likelihood is another Gamma density:
      </p>
      <div class="eq">
        <Tex
          display
          e="\lambda_d\mid N_d,c_d,R_d,\theta\sim\mathrm{Gamma}\!\left(\theta+N_d,\frac{\theta}{R_d}+c_d\right)"
        />
      </div>
      <p>
        The vertical bar means “given”: the same intensity is now informed by <Tex e="N_d" /> as
        well as coverage and the fitted model’s parameters. Its updated mean is the first Gamma
        parameter divided by the second, which can also be written as a weighted average:
      </p>
      <div class="eq">
        <Tex
          display
          e="\widehat\lambda_d=\frac{\theta+N_d}{\theta/R_d+c_d}=(1-w_d)R_d+w_d\frac{N_d}{c_d}"
        />
      </div>
      <p>
        The weight <Tex e="w_d=c_dR_d/(\theta+c_dR_d)" /> determines how much we learn from the
        observed part. More coverage gives the observed count more weight. If the count is above the
        expected <Tex e="c_dR_d" />, the correction raises the missing-passage estimate; if it is
        below, the correction lowers it.
      </p>
      <p>We use this updated intensity to estimate the missing birds:</p>
      <div class="eq"><Tex display e="\widehat M_d=(1-c_d)\widehat\lambda_d" /></div>
      <h6>Allow flocks to concentrate passage within the day</h6>
      <p>
        This next step leaves the expected missing count unchanged; it adds variability to account
        for flocking. The Poisson step assumes independent bird passages once the day’s intensity is
        known. Because the same intensity <Tex e="\lambda_d" /> applies to counted and uncounted
        hours, a busy count informs the rest of the day. But birds travelling in flocks also create
        bursts within that daily pattern. This extra clustering must be accounted for when filling
        uncounted hours, so the uncertainty reflects birds arriving together. We describe it with a
        <a
          href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.dirichlet_multinomial.html"
          >Dirichlet–multinomial distribution</a
        >, with its own dispersion <Tex e="\kappa" />. The two dispersions describe different
        things: <Tex e="\theta" /> is the spread between days, how much a day’s passage departs from
        its expectation; <Tex e="\kappa" /> is the clustering of birds within a day, how unevenly
        that passage falls across its hours.
      </p>
      <p>
        To estimate it, we add the hourly counts into fixed four-hour blocks within each day. For
        each counted block <Tex e="b" />, <Tex e="n_{d,b}" /> is its bird count and
        <Tex e="a_{d,b}" /> is the share of the full-day profile covered by counting in that block.
        Given their daily sum <Tex e="n_d=\sum_b n_{d,b}" />, the block counts follow:
      </p>
      <div class="eq">
        <Tex
          display
          e="(n_{d,1},\ldots,n_{d,B})\mid n_d\sim\mathrm{DM}\!\left(n_d,\kappa\boldsymbol a_d\right)"
        />
      </div>
      <p>
        Here DM denotes the Dirichlet–multinomial distribution, and
        <Tex e="\boldsymbol a_d" /> collects the counted blocks’ profile shares. The expected
        fraction of counted birds in block <Tex e="b" /> is <Tex e="a_{d,b}/\sum_b a_{d,b}" />.
        Actual fractions can depart from these expectations: smaller <Tex e="\kappa" /> allows
        stronger clustering, while larger values keep them closer to the profile. We fit one
        <Tex e="\kappa" /> per taxon using days with at least two counted blocks.
      </p>
      <p>
        For a given intensity <Tex e="\lambda_d" />, let <Tex e="m_d=(1-c_d)\lambda_d" /> be the
        expected missing count. We use the fitted <Tex e="\kappa" /> to add extra variance to the
        missing birds <Tex e="M_d" />:
      </p>
      <div class="eq">
        <Tex
          display
          e="M_d\mid\lambda_d\sim\operatorname{NegBin}(m_d,\kappa(1-c_d)),\qquad \operatorname{Var}(M_d\mid\lambda_d)=m_d+\frac{m_d^2}{\kappa(1-c_d)}"
        />
      </div>
      <p>
        The first term is Poisson variance; the second accounts for flocking. Smaller
        <Tex e="\kappa" /> makes this extra variance larger, while the mean remains <Tex e="m_d" />.
        This is a negative-binomial prediction for missing hours. Uncertainty in
        <Tex e="\lambda_d" /> adds further variability; adding the fixed observed count
        <Tex e="N_d" /> gives the uncertainty in the reconstructed total. The estimate published on
        the species pages averages 1 000 joint reconstruction draws, including coefficient
        uncertainty; the 2.5th and 97.5th percentiles give its 95% interval.
      </p>
      <ConditionalDay
        v-if="data.trend"
        :theta="data.trend.theta"
        :kappa="data.trend.kappa"
        :name="name"
        :profile="data.profile.day"
        :year="data.trend.last_year"
      />
    </section>
    <section id="reconstruction-m-draws">
      <h5><span class="sec-n">3</span>Inspect reconstructed days</h5>
      <p v-if="data.trend">
        The figure shows every day of one season: the birds counted, and the reconstructed full-day
        total with its 95% interval.<span class="screen-only">
          Choose a day to see how its total is made.</span
        >
      </p>
      <figure v-if="data.trend" class="figure w-100">
        <div class="reconstruction-controls">
          <YearSelector
            id="reconstruction-year"
            v-model="year"
            :years="years"
            context="reconstruction"
          />
          <label for="reconstruction-day"
            >Day
            <div class="input-group input-group-sm navigation-control">
              <button
                class="btn btn-outline-secondary"
                type="button"
                aria-label="Previous reconstruction day"
                :disabled="selectedRow.date === rows[0].date"
                @click="
                  selectedDate = rows[rows.findIndex((r) => r.date === selectedRow.date) - 1].date
                "
              >
                ‹</button
              ><select
                id="reconstruction-day"
                :value="selectedRow.date"
                class="form-select form-select-sm"
                @change="selectedDate = $event.target.value"
              >
                <option v-for="row in rows" :key="row.date" :value="row.date">
                  {{ dateLabel(row.date) }}
                </option></select
              ><button
                class="btn btn-outline-secondary"
                type="button"
                aria-label="Next reconstruction day"
                :disabled="selectedRow.date === rows.at(-1).date"
                @click="
                  selectedDate = rows[rows.findIndex((r) => r.date === selectedRow.date) + 1].date
                "
              >
                ›
              </button>
            </div></label
          >
        </div>
        <div ref="dailyDiv" class="plot-md"></div>
        <div class="day-breakdown" aria-live="polite">
          <strong
            >{{ dateLabel(selectedRow.date) }} · observed coverage
            {{ (100 * selectedRow.originalC).toFixed(1) }}%</strong
          >
          <ObservedDayProfile
            v-if="methodProfile && methodEffort"
            :row="selectedRow"
            :predicted="predicted"
            :theta="data.trend.theta"
            :profile="methodProfile"
            :slots="methodEffort[selectedRow.date] ?? []"
          />
          <p v-else class="small">
            The export gives the daily coverage; date-specific profile inputs are unavailable.
          </p>
          <div v-for="row in comparison" :key="row.label" class="daily-comparison-row">
            <span>{{ row.label }} <Tex v-if="row.tex" :e="row.tex" /></span>
            <div class="daily-comparison-track">
              <div
                :style="{ width: `${(100 * row.value) / comparisonMax}%`, background: row.color }"
              ></div>
              <span
                v-if="row.interval"
                class="daily-comparison-interval"
                :style="{
                  left: `${(100 * row.interval[0]) / comparisonMax}%`,
                  width: `${(100 * (row.interval[1] - row.interval[0])) / comparisonMax}%`,
                }"
                :title="`95% interval: ${fmt(row.interval[0])}–${fmt(row.interval[1])}`"
              ></span>
            </div>
            <strong
              >{{ fmt(row.value)
              }}<small v-if="row.interval" class="d-block"
                >95%: {{ fmt(row.interval[0]) }}–{{ fmt(row.interval[1]) }}</small
              ></strong
            >
          </div>
        </div>
        <figcaption class="figure-caption">
          <strong>Figure 3.2.</strong> {{ name }}, {{ year }}: counts (red bars), reconstructed
          means (blue dots) and 95% intervals (black vertical lines), with one day broken down
          below.<span class="screen-only">
            Click a day or use the selector to compare coverage, prediction and
            reconstruction.</span
          >
        </figcaption>
      </figure>
      <p v-else class="callout callout-info">
        {{ name }} has no fitted model-based daily reconstruction.
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS, alpha } from "../../../theme.js";
import Tex from "../Tex.vue";
import YearSelector from "../YearSelector.vue";
import ObservedDayProfile from "../ObservedDayProfile.vue";
import ConditionalDay from "../ConditionalDay.vue";
const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});
const methodProfile = ref(null),
  methodEffort = ref(null);
watch(
  () => props.data.taxon_id,
  async (id) => {
    methodProfile.value = null;
    const [profile, effort] = await Promise.all([
      fetch(`./data/methods/${id}.json`),
      fetch("./data/methods/effort.json"),
    ]);
    if (profile.ok && effort.ok) {
      methodProfile.value = await profile.json();
      methodEffort.value = await effort.json();
    }
  },
  { immediate: true },
);
const years = computed(() => props.data.trend?.annual.map((r) => r.year).reverse() ?? []);
const year = ref(years.value[0]),
  selectedDate = ref(null);
const originalCoverage = computed(
  () =>
    new Map(
      props.data.days.date
        .map((date, i) => [date, props.data.days.c[i]])
        .filter(([, c]) => c != null),
    ),
);
const cases = computed(() => {
  const d = props.data.trend?.days;
  const c = d?.date.map((date, i) => originalCoverage.value.get(date) ?? d.c[i]);
  if (!c) return null;
  const none = c.filter((v) => v < props.data.trend.min_coverage).length,
    full = c.filter((v) => v === 1).length;
  return {
    none: ((100 * none) / c.length).toFixed(1),
    full: ((100 * full) / c.length).toFixed(1),
    partial: ((100 * (c.length - none - full)) / c.length).toFixed(1),
  };
});
const rows = computed(() => {
  const d = props.data.trend?.days;
  return d
    ? d.date.flatMap((date, i) =>
        date.startsWith(`${year.value}-`)
          ? [
              {
                date,
                c: d.c[i],
                conditioningC: d.c[i] >= props.data.trend.min_coverage ? d.c[i] : 0,
                originalC: originalCoverage.value.get(date) ?? d.c[i],
                count: d.count[i],
                total: d.total[i],
                lo: d["q2.5"][i],
                hi: d["q97.5"][i],
              },
            ]
          : [],
      )
    : [];
});
const selectedRow = computed(
  () =>
    rows.value.find((r) => r.date === selectedDate.value) ??
    rows.value.reduce(
      (best, r) => (r.total - r.count > best.total - best.count ? r : best),
      rows.value[0],
    ),
);
const predicted = computed(() => {
  const row = selectedRow.value;
  if (!row) return null;
  const episodes = props.data.trend.episodes;
  const [, m, d] = row.date.split("-").map(Number);
  const doy = (Date.UTC(2001, m - 1, d) - Date.UTC(2001, 0, 1)) / 86400000 + 1;
  const i = episodes.doy.indexOf(doy),
    y = String(year.value);
  return episodes.base[y][i] * Math.exp(episodes.weather[y][i] + episodes.episode[y][i]);
});
const comparison = computed(() => {
  const r = selectedRow.value;
  if (!r) return [];
  return [
    { label: "Observed count", tex: "N_d", value: r.count, color: COLORS.counted },
    {
      label: "Expected full-day passage",
      tex: "R_d",
      value: predicted.value,
      color: COLORS.faint,
    },
    {
      label: "Reconstructed total",
      tex: "\\widehat F_d",
      value: r.total,
      color: COLORS.predicted,
      interval: [r.lo, r.hi],
    },
  ];
});
const comparisonMax = computed(() =>
  Math.max(1, ...comparison.value.map((r) => r.interval?.[1] ?? r.value)),
);
const fmt = (value) => value.toLocaleString("en", { maximumFractionDigits: 1 });
const dateLabel = (date) =>
  new Date(`${date}T12:00:00Z`).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
const dailyDiv = ref(null),
  visible = usePlot(dailyDiv);
async function plot() {
  if (!visible.value || !dailyDiv.value) return;
  const d = rows.value,
    x = d.map((r) => r.date),
    custom = d.map((r) => [r.date, r.count, r.c, r.total, r.lo, r.hi]);
  await plotReact(
    dailyDiv.value,
    [
      {
        x,
        y: d.map((r) => r.count),
        type: "bar",
        width: 86400000 * 0.82,
        marker: { color: alpha(COLORS.counted, 0.55) },
        name: "Counted",
        customdata: custom,
        hovertemplate:
          "%{x|%d %b}: %{y:,.0f} counted<br>Coverage %{customdata[2]:.0%}<extra></extra>",
      },
      {
        x: d.flatMap((r) => [r.date, r.date, null]),
        y: d.flatMap((r) => [r.lo, r.hi, null]),
        mode: "lines",
        line: { color: COLORS.ink, width: 1.5 },
        name: "95% interval",
        customdata: custom.flatMap((r) => [r, r, null]),
        hoverinfo: "skip",
      },
      {
        x,
        y: d.map((r) => r.total),
        mode: "markers",
        marker: { size: 4, color: COLORS.predicted },
        name: "Estimated total (mean)",
        customdata: custom,
        hovertemplate: "%{x|%d %b}: %{y:,.1f} full-day mean<extra></extra>",
      },
    ],
    {
      margin: { t: 40, l: 55, r: 8, b: 35 },
      barmode: "overlay",
      showlegend: true,
      legend: { orientation: "h", y: 1.18, font: { size: 10 } },
      xaxis: { type: "date", fixedrange: true, tickformat: "%d %b", dtick: "M1" },
      yaxis: { fixedrange: true, title: { text: "birds per day" }, rangemode: "tozero" },
      shapes: [
        {
          type: "rect",
          x0: Date.parse(`${selectedRow.value.date}T00:00:00Z`) - 43200000,
          x1: Date.parse(`${selectedRow.value.date}T00:00:00Z`) + 43200000,
          yref: "paper",
          y0: 0,
          y1: 1,
          fillcolor: alpha(COLORS.accent, 0.12),
          line: { width: 0 },
          layer: "below",
        },
      ],
    },
    { displayModeBar: false, responsive: true },
  );
  dailyDiv.value.removeAllListeners("plotly_click");
  dailyDiv.value.on("plotly_click", (event) => {
    selectedDate.value = event.points[0].customdata[0];
  });
}
watch(year, () => {
  const mmdd = selectedDate.value?.slice(5);
  if (mmdd)
    selectedDate.value =
      rows.value.find((r) => r.date.slice(5) === mmdd)?.date ?? rows.value[0].date;
});
watch(() => [visible.value, year.value, props.data, selectedRow.value?.date], plot);
</script>
