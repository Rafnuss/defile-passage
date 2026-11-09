<template>
  <div>
    <MethodCoverage :name="name" :data="data" :effort="effort" />
    <p v-if="!data.trend" class="callout callout-info">
      {{ name }} has no fitted daily count model. Its coverage is still available above; choose a
      species such as Red Kite to see the model illustrations.
    </p>
    <template v-if="data.trend">
      <section id="model-m-scatter">
        <h5><span class="sec-n">2</span>The count distribution</h5>
        <p>
          If birds passed independently, the observed daily count <Tex e="N_d" /> would follow a
          <strong>Poisson</strong> distribution, whose variance equals its mean. Real counts vary
          more because birds may travel in flocks and days differ in ways the model cannot fully
          explain. We therefore use a <strong>negative binomial</strong> distribution to model the
          observed counts <Tex e="N_d" />, with expected observed count <Tex e="\mu_d" /> and extra
          variation controlled by <Tex e="\theta" />:
        </p>
        <div class="eq">
          <Tex
            display
            e="N_d \sim \operatorname{NegBin}(\mu_d,\ \theta), \qquad \operatorname{Var}(N_d) = \mu_d + \frac{\mu_d^2}{\theta} \tag{3}"
          />
        </div>
        <p>
          Compared with a Poisson distribution with the same mean <Tex e="\mu_d" />, the variance is
          increased by <Tex e="\mu_d^2/\theta" />. A small value of <Tex e="\theta" /> allows much
          greater variation between days; as the value of <Tex e="\theta" /> grows, the distribution
          approaches the Poisson. We estimate one <Tex e="\theta" /> for each species, jointly with
          the model’s smoothing parameters (section 4).
        </p>
        <NegBinWidget :name="name" :species-theta="trend.theta" />
      </section>
      <section id="model-m-model">
        <h5><span class="sec-n">3</span>The model</h5>
        <p>
          We model the expected full-day passage <Tex e="R_d" /> as a function of the year, date and
          weather, then use the coverage to relate it to the observed count, through
          <Tex e="\log \mu_d = \log c_d + \log R_d" />. For day&nbsp;<Tex e="d" />,
          <Tex e="y_d" /> denotes its year and <Tex e="s_d" /> its day of year:
        </p>
        <div class="eq">
          <Tex
            display
            e="\log R_d = \alpha + \Tr(y_d) + \Yr_{y_d} + \Se(s_d) + \Sh(y_d,s_d) + \Wx_d + \Ep_{y_d}(s_d) \tag{4}"
          />
        </div>
        <p>Each term describes a source of variation known to influence the passage:</p>
        <table class="terms">
          <thead>
            <tr>
              <th></th>
              <th>Term</th>
              <th>What it describes</th>
              <th>Form and prior</th>
            </tr>
          </thead>
          <tbody v-for="g in GROUPS" :key="g.name">
            <tr>
              <th colspan="4" class="terms-group">{{ g.name }}</th>
            </tr>
            <tr v-for="term in g.terms" :key="term.name">
              <td class="terms-sym"><Tex :e="term.tex" /></td>
              <th scope="row" :class="term.cls">{{ term.name }}</th>
              <td>{{ term.text }}</td>
              <td class="terms-form">{{ term.form }}</td>
            </tr>
          </tbody>
        </table>
        <p>
          The terms are added on the logarithmic scale, so they <em>multiply</em> the number of
          birds. An increase of 0.1 in any term means about 10% more expected birds, holding the
          other terms fixed.
        </p>

        <h6 class="model-timescale">Over the years</h6>
        <figure class="figure w-100">
          <div class="row g-2">
            <div class="col-md-6">
              <div class="panel-title t-trend">
                a. Smooth total · combining <Tex e="\Tr,\Se,\Sh" />
              </div>
              <div ref="trendDiv" class="plot-sm"></div>
            </div>
            <div class="col-md-6">
              <div class="panel-title t-year">
                b. Season / smooth total · combining <Tex e="\Yr,\Wx,\Ep" />
              </div>
              <div ref="yearDiv" class="plot-sm"></div>
            </div>
          </div>
          <figcaption class="figure-caption">
            <strong>Figure 2.3.</strong> Summaries of the fitted model for {{ name }}.
            <strong>a.</strong> The smooth season total relative to {{ trend.first_year }}, with its
            95% interval: the base level with the effects of the trend <Tex e="\Tr" />, the season
            <Tex e="\Se" /> and the change of timing <Tex e="\Sh" />, summed over the season.
            <strong>b.</strong> Each year’s reconstructed total divided by its smooth total: what
            the effects of the year level <Tex e="\Yr" />, the weather <Tex e="\Wx" /> and the
            episodes <Tex e="\Ep" /> add to it. Values above 1 indicate more passage than the smooth
            expectation.
          </figcaption>
        </figure>
        <h6 class="model-timescale">Over the season</h6>
        <p id="model-m-timing">
          <strong class="t-shift">Change of timing</strong>, <Tex e="\Sh(y,s)" />. Migration
          phenology can change over decades: populations may alter when they migrate, or populations
          passing at different times may change in relative abundance. We represent this gradual
          change with a smooth interaction between year and day of year.
        </p>
        <p>
          Together, the two terms give each year its own seasonal shape: <Tex e="\Se(s)" /> is the
          average seasonal pattern shared across years, and <Tex e="\Sh(y,s)" /> its gradual
          departure in year <Tex e="y" />. The short-lived peaks and gaps of individual seasons are
          left to the effects of weather and episodes, not to this long-term change.
        </p>
        <figure class="figure w-100">
          <label for="shape-year" class="form-label"
            >Seasonal shape · combining <Tex e="\Se,\Sh" /> ·
            <strong>{{ shapeYear }}</strong></label
          >
          <input
            id="shape-year"
            v-model.number="shapeYear"
            type="range"
            class="form-range"
            :min="shapeYears[0]"
            :max="shapeYears.at(-1)"
            step="1"
          />
          <div ref="seasonDiv" class="plot-md"></div>
          <figcaption class="figure-caption">
            <strong>Figure 2.4.</strong> {{ name }}: the fitted seasonal shape in
            {{ shapeYear }} (solid), with {{ shapeYears[0] }} and {{ shapeYears.at(-1) }} as dotted
            references. Each curve integrates to one; it is drawn without the effects of weather and
            episodes.
          </figcaption>
        </figure>
        <h6 id="model-m-days" class="model-timescale">From day to day</h6>
        <p id="model-m-weather"><strong class="t-weather">Effect of weather</strong></p>
        <p>
          We use hourly
          <a href="https://open-meteo.com/en/docs/historical-weather-api"
            >ERA5 data from the Open-Meteo archive</a
          >
          at the Défilé (0.25° grid). Each daily weather variable is calculated from hourly values,
          then averaged across the species’ expected flight hours:
        </p>
        <ol>
          <li>
            <strong>Align the hourly measurements.</strong> Precipitation and sunshine are totals
            for the preceding hour. Other measurements are averaged between the hour’s endpoints.
          </li>
          <li>
            <strong>Calculate nine hourly variables:</strong>
            <ol class="weather-variables">
              <li>
                <strong>Precipitation</strong> (<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>precipitation</code></a
                >): <Tex e="\log(1+\text{mm per hour})" />.
              </li>
              <li>
                <strong>Previous-day precipitation:</strong> the same
                <a href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>precipitation</code></a
                >
                transformation, shifted by 24 hours.
              </li>
              <li>
                <strong>Sunshine</strong> (<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>sunshine_duration</code></a
                >): the fraction of the hour with direct sunshine, distinguishing sunny conditions
                from overcast conditions.
              </li>
              <li>
                <strong>Thermal mixing</strong> (<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>boundary_layer_height</code></a
                >): the depth of the atmosphere mixed by turbulence near the ground. A deeper layer
                can support higher thermal soaring, though it is not a direct measurement of the
                thermals used by birds.
              </li>
              <li>
                <strong>Eastward wind, <Tex e="u" />:</strong> derived from
                <a href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>wind_speed_100m</code></a
                >
                and
                <a href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>wind_direction_100m</code></a
                >, in m/s.
              </li>
              <li>
                <strong>Northward wind, <Tex e="v" />:</strong> the northward component of the same
                <a href="https://open-meteo.com/en/docs/historical-weather-api">100 m wind vector</a
                >, in m/s.
              </li>
              <li>
                <strong>Wind speed, <Tex e="\sqrt{u^2+v^2}" />:</strong>
                <a href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>wind_speed_100m</code></a
                >, in m/s.
              </li>
              <li>
                <strong>Pressure change</strong> (<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>pressure_msl</code></a
                >): for each hour, sea-level pressure minus its value 24 hours earlier, in hPa.
                These hourly changes are then averaged in step 3.
              </li>
              <li>
                <strong>Temperature anomaly</strong> (<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
                  ><code>temperature_2m</code></a
                >): temperature minus the historical mean for the same date and UTC hour, smoothed
                over a 31-day calendar window, in °C.
              </li>
            </ol>
          </li>
          <li>
            <strong>Average over the day.</strong> Weight the hourly values by the species’
            time-of-day profile, including hours not counted. This gives the weather during expected
            passage, rather than a simple 24-hour mean.
          </li>
          <li>
            <strong>Put variables on a common scale.</strong> Subtract each variable’s mean and
            divide by its standard deviation on counted days, giving <Tex e="w_{j,d}" />.
          </li>
        </ol>
        <div class="eq"><Tex display e="\Wx_d = \sum_{j=1}^{9}\beta_j w_{j,d}" /></div>
        <p>
          Here <Tex e="w_{j,d}" /> is weather variable <Tex e="j" /> for day <Tex e="d" />, after
          standardisation. Its fitted coefficient <Tex e="\beta_j" /> says how that variable changes
          log expected passage, holding the other terms fixed. Their sum <Tex e="\Wx_d" /> is the
          combined effect of the day’s weather.
        </p>
        <WeatherPanels v-if="data.weather" :weather="data.weather" :name="name" />
        <p>
          <strong class="t-episode">Episodes</strong>, <Tex e="\Ep_y(s)" />. Migration often
          contains runs of unusually busy or quiet days. These may reflect weather elsewhere or
          earlier along the route, the arrival of particular populations, social behaviour, or other
          processes. The episode term represents the remaining pattern shared by neighbouring days
          after accounting for the model’s seasonal and local-weather effects; it does not identify
          its ecological cause.
        </p>
        <p>
          Each year has its own spline along day of year, built from smoothly joined cubic
          polynomial pieces. In well-covered seasons, observations before and after a missing day
          constrain the surrounding migration wave, helping reconstruct short gaps. This is
          particularly useful with our near-continuous counting. Across a long gap, the observations
          provide much less information about where a wave occurred.
        </p>
        <EpisodeWidget
          v-if="trend.episodes && data.days"
          :name="name"
          :episodes="trend.episodes"
          :days="trend.days"
          :theta="trend.theta"
          :min-coverage="trend.min_coverage"
        />
      </section>
      <section id="model-m-smooth">
        <h5><span class="sec-n">4</span>How smooth is smooth?</h5>
        <p>
          Each curve (<Tex e="\Tr" />, <Tex e="\Se" />, <Tex e="\Sh" />, <Tex e="\Ep" />) is a
          <em>spline</em>: a chain of short polynomial pieces joined smoothly, flexible enough to
          follow almost any shape. Too flexible, it would follow random fluctuations. Smoothness and
          size penalties regularise the fit. For the smoothness terms, the coefficient fit maximises
        </p>
        <div class="eq">
          <Tex
            display
            e="\text{log-likelihood of the counts} \;-\; \sum_k \rho_k \times \text{wiggliness}_k \tag{5}"
          />
        </div>
        <p>
          A large smoothing parameter <Tex e="\rho_k" /> favours a simpler curve; a small one lets
          it bend more. Smoothing parameters and <Tex e="\theta" /> are estimated using an
          approximation to the <em>marginal likelihood</em>, which accounts for uncertainty in the
          coefficients. The long-term trend describes gradual change across years. The year levels
          <Tex e="\Yr" /> are there for year-to-year jumps. The weather effects
          <Tex e="\beta_j" /> are straight lines, with a fixed penalty of their own: without a clear
          signal in the counts, an effect stays near zero.
        </p>
        <SmoothWidget :name="name" :annual="trend.annual" />
      </section>
      <section id="model-m-fit">
        <h5><span class="sec-n">5</span>Fitting the model</h5>
        <p>
          Before predicting passage, we need to fit the model: learn the parameters of its
          components from the observed daily counts. The fitting estimates two groups of parameters:
        </p>
        <ul>
          <li>
            <strong>Coefficients</strong> determine the height and shape of the curves and the size
            of the year and weather effects. Together, they determine the predicted passage on each
            day.
          </li>
          <li>
            <strong>Smoothing parameters and count dispersion.</strong> Smoothing parameters control
            how strongly curves are kept smooth and effects are kept small. The dispersion parameter
            <Tex e="\theta" /> of the negative binomial distribution (section 2) controls the
            remaining variability of daily counts around their predicted values.
          </li>
        </ul>
        <p>
          Each group of coefficients has the prior given in the table of section 3: it keeps curves
          smooth and effects small unless the counts support more. The strength of these priors, all
          but the weather’s, is estimated from the counts too, together with <Tex e="\theta" />. The
          fitting therefore alternates between the two groups of parameters:
        </p>
        <ol>
          <li>
            <strong>Estimate the coefficients.</strong> An iterative solver adjusts all coefficients
            together to improve agreement with the counts while respecting the prior penalties,
            keeping smoothing parameters and dispersion fixed during this step.
          </li>
          <li>
            <strong>Update smoothing and dispersion.</strong> Using the current fit, update the
            smoothing parameters and the count-dispersion parameter <Tex e="\theta" />.
          </li>
          <li>
            <strong>Repeat.</strong> Re-estimate the coefficients under those updated settings,
            continuing until the changes are small or the iteration limits are reached.
          </li>
        </ol>
        <p>
          Estimating the strength of the priors from the data, then the coefficients given them, is
          known as <strong>empirical Bayes</strong>. After fitting, a joint Gaussian approximation
          describes uncertainty around the coefficient estimates. Draws from that approximation
          produce plausible combinations of curves and effects. Chapter 3 uses them to draw the
          birds missed during uncounted periods.
        </p>
        <p>
          For fitting, we use daily counts with coverage of at least
          {{ Math.round(100 * trend.min_coverage) }}% (<Tex :e="`c_d\\ge${trend.min_coverage}`" />)
          to avoid estimating full-day passage from very short observations that may happen to
          contain a flock.
        </p>
        <details class="method-detail">
          <summary>Solver details</summary>
          <p>
            The fit follows the generalised additive models of
            <a href="https://doi.org/10.1201/9781315370279">Wood (2017)</a>. The coefficients are
            estimated by penalised iteratively reweighted least squares (P-IRLS); the smoothing
            parameters and <Tex e="\theta" /> by maximising a Laplace approximation of the marginal
            likelihood, with the extended Fellner–Schall update of
            <a href="https://doi.org/10.1111/biom.12666">Wood and Fasiolo (2017)</a>.
          </p>
          <p>
            The implementation uses Python with
            <a href="https://numpy.org/doc/stable/">NumPy</a> for arrays and
            <a href="https://docs.scipy.org/doc/scipy/">SciPy</a> for splines, linear algebra and
            optimisation.
          </p>
          <p>
            The fitting uses empirical Bayes. Gaussian priors on the coefficients become penalties
            in the optimisation: at fixed smoothing and dispersion, the solver maximises the
            negative-binomial log-likelihood minus those penalties, giving the posterior mode.
            Smoothing and dispersion are selected using a Laplace approximation to the marginal
            likelihood, which accounts for uncertainty in the coefficients. Subsequent uncertainty
            calculations treat these estimated settings as fixed.
          </p>
          <ul>
            <li>
              <strong>Curves as coefficients.</strong> Cubic B-spline basis functions turn each
              curve into a weighted sum of fixed smooth pieces. Nominal basis sizes, before
              constraints, are 12 for the year trend, 20 for the season, 6 × 8 for the timing
              interaction and 25 per year for episodes. Penalties limit how much adjacent
              coefficients differ: second differences for the main smooths, first differences plus a
              size penalty for episodes.
            </li>
            <li>
              <strong>Counting effort in the likelihood.</strong> The model fits
              <Tex e="\log\mu_d=\log c_d+\log R_d" />. The known <Tex e="\log c_d" /> term is an
              offset: its coefficient is fixed at one rather than estimated.
            </li>
            <li>
              <strong>Coefficient solver.</strong> Penalised iteratively reweighted least squares
              (Fisher scoring) finds the posterior mode at fixed smoothing and dispersion. Steps are
              halved if they lower the objective. Cholesky factors and a Schur complement solve the
              shared and per-year episode blocks without a single large dense inverse.
            </li>
            <li>
              <strong>Smoothing and dispersion.</strong> Extended Fellner–Schall updates estimate
              the smoothing penalties. Bounded scalar optimisation updates the same
              <Tex e="\theta" /> used in the negative binomial, alternating with smoothing updates
              under a Laplace-approximated marginal likelihood.
            </li>
            <li>
              <strong>Weather coefficients.</strong> Each taxon has its own <Tex e="\beta_j" />.
              Standardised coefficients have a fixed unit-precision Gaussian prior (standard
              deviation one), shrinking weak effects towards zero. Year levels also have a size
              penalty.
            </li>
            <li>
              <strong>Stopping and bounds.</strong> Coefficient updates allow 100 iterations with
              relative objective tolerance <Tex e="10^{-8}" />. Smoothing updates allow 100
              iterations with tolerance 0.01 on changes in log parameters; the outer
              dispersion/smoothing loop allows five rounds. <Tex e="\theta" /> is bounded to
              0.02–200 and log smoothing parameters to −6–16; a coefficient ridge of
              <Tex e="10^{-4}" /> stabilises null spaces.
            </li>
            <li>
              <strong>Uncertainty approximation.</strong> Joint Gaussian coefficient draws use the
              penalised information matrix. Its low-rate information floor is 0.1 birds per full
              day, scaled by coverage; this stabilises near-empty tails and enters the Laplace
              marginal likelihood, without replacing fitted mean counts. Smoothing, dispersion and
              the coverage profile stay fixed across draws.
            </li>
          </ul>
        </details>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { usePlot, plotReact } from "../../../utils/usePlot";
import { COLORS, MODEL_COLORS, alpha } from "../../../theme.js";
import { doyLabel } from "../../../services/explore";
import Tex from "../Tex.vue";
import NegBinWidget from "../NegBinWidget.vue";
import EpisodeWidget from "../EpisodeWidget.vue";
import SmoothWidget from "../SmoothWidget.vue";
import MethodCoverage from "./MethodCoverage.vue";
import WeatherPanels from "../WeatherPanels.vue";

const { locale } = useI18n();

const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, required: true },
  effort: { type: Array, default: null },
});

// The terms of eq. (4), in the order of the equation, by time scale
const GROUPS = [
  {
    name: "Over the years",
    terms: [
      {
        tex: "\\alpha",
        name: "level",
        cls: "",
        text: "The baseline log passage rate: it sets the scale of expected birds per full day, around which the other terms raise or lower passage.",
        form: "One constant, no prior.",
      },
      {
        tex: "\\Tr(y)",
        name: "trend",
        cls: "t-trend",
        text: "A smooth change across years, generally associated with long-term population change but also with shifts in migration routes or visibility at this site.",
        form: "Smooth curve of the year (spline, 12 coefficients); prior: smoothness, its strength estimated.",
      },
      {
        tex: "\\Yr_y",
        name: "year level",
        cls: "t-year",
        text: "One value per year: good and bad years around the trend (breeding success, a shifted route, …).",
        form: "Random effect: one level per year; prior: levels near zero, their spread estimated.",
      },
    ],
  },
  {
    name: "Over the season",
    terms: [
      {
        tex: "\\Se(s)",
        name: "season",
        cls: "t-season",
        text: "The average shape of the season: when the species passes, and how spread out.",
        form: "Smooth curve of the day of year (spline, 20 coefficients); prior: smoothness, its strength estimated.",
      },
      {
        tex: "\\Sh(y,s)",
        name: "change of timing",
        cls: "t-shift",
        text: "A slow change of that shape over the decades, for example a season starting earlier or lasting longer.",
        form: "Smooth surface of year and day of year (spline, 6 × 8 coefficients); prior: smoothness, its strength estimated.",
      },
    ],
  },
  {
    name: "From day to day",
    terms: [
      {
        tex: "\\Wx_d",
        name: "weather",
        cls: "t-weather",
        text: "The effect of the day's weather: rain, sunshine, thermals, wind, fronts and temperature (below).",
        form: "Fixed effects: one coefficient for each of 9 standardised weather variables; prior: near zero, of fixed strength.",
      },
      {
        tex: "\\Ep_y(s)",
        name: "episodes",
        cls: "t-episode",
        text: "Runs of a few good or bad days that the weather does not explain (below).",
        form: "Smooth random effect: a curve of the day of year for each year (spline, 25 coefficients each); prior: small, smooth day to day, its strength estimated.",
      },
    ],
  },
];
// Term colours, as in the CSS below (.t-*)
const C = MODEL_COLORS;
const LOG_TICKS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50];

const trendDiv = ref(null);
const yearDiv = ref(null);
const seasonDiv = ref(null);
const piecesVisible = usePlot(trendDiv);
usePlot(yearDiv);
const seasonVisible = usePlot(seasonDiv);

const trend = computed(() => props.data.trend);
const annual = computed(() => trend.value.annual);
const shapeYears = computed(() =>
  Object.keys(trend.value.episodes.base)
    .map(Number)
    .sort((a, b) => a - b),
);
const shapeYear = ref(props.data.trend ? shapeYears.value.at(-1) : null);
const CONFIG = { displayModeBar: false, responsive: true };
const baseLayout = (extra = {}) => ({
  margin: { t: 8, l: 48, r: 8, b: 36 },
  dragmode: false,
  autosize: true,
  showlegend: false,
  font: { size: 11 },
  ...extra,
});

function plotPieces() {
  if (!piecesVisible.value) return;
  const a = annual.value;
  const year = a.map((r) => r.year);
  const s0 = a[0].smooth;
  if (trendDiv.value) {
    plotReact(
      trendDiv.value,
      [
        {
          x: [...year, ...year.slice().reverse()],
          y: [
            ...a.map((r) => r["smooth_q97.5"] / s0),
            ...a.map((r) => r["smooth_q2.5"] / s0).reverse(),
          ],
          fill: "toself",
          fillcolor: alpha(C.trend, 0.15),
          line: { color: "transparent" },
          hoverinfo: "skip",
        },
        {
          x: year,
          y: a.map((r) => r.smooth / s0),
          mode: "lines",
          line: { color: C.trend, width: 2.5 },
          hovertemplate: "%{x}: ×%{y:.2f}<extra></extra>",
        },
      ],
      baseLayout({
        xaxis: { fixedrange: true },
        yaxis: {
          type: "log",
          fixedrange: true,
          title: { text: `× ${a[0].year}` },
          tickvals: LOG_TICKS,
          ticktext: LOG_TICKS.map((v) => `×${v}`),
        },
        shapes: [hline(1)],
      }),
      CONFIG,
    );
  }
  if (yearDiv.value) {
    const ratio = a.map((r) => r.total / r.smooth);
    plotReact(
      yearDiv.value,
      [
        {
          x: year,
          y: ratio.map((v) => v - 1),
          base: 1,
          type: "bar",
          marker: { color: ratio.map((v) => (v >= 1 ? C.year : alpha(C.year, 0.45))) },
          customdata: ratio,
          hovertemplate: "%{x}: ×%{customdata:.2f} the trend<extra></extra>",
        },
      ],
      baseLayout({
        bargap: 0.15,
        xaxis: { fixedrange: true },
        yaxis: { fixedrange: true, title: { text: "total / trend" } },
        shapes: [hline(1)],
      }),
      CONFIG,
    );
  }
}
function plotSeason() {
  if (!seasonVisible.value || !seasonDiv.value) return;
  const { doy, base } = trend.value.episodes;
  const normalise = (v) => v.map((n) => n / v.reduce((a, b) => a + b, 0));
  const first = shapeYears.value[0],
    last = shapeYears.value.at(-1),
    selected = shapeYear.value;
  const ticks = [213, 244, 274, 305];
  plotReact(
    seasonDiv.value,
    [first, last, selected].map((year, i) => ({
      x: doy,
      y: normalise(base[year]),
      mode: "lines",
      name: i === 2 ? `${year} selected` : `${year} reference`,
      line: {
        color: i === 2 ? COLORS.plum : i === 1 ? COLORS.faint : COLORS.historyInner,
        width: i === 2 ? 2.5 : 1.5,
        dash: i === 2 ? "solid" : "dot",
      },
      text: doy.map((d) => doyLabel(d, locale.value)),
      hovertemplate: "%{text}: %{y:.1%}<extra>%{fullData.name}</extra>",
    })),
    baseLayout({
      showlegend: true,
      legend: { orientation: "h", y: 1.12 },
      xaxis: {
        fixedrange: true,
        tickvals: ticks,
        ticktext: ticks.map((d) => doyLabel(d, locale.value)),
      },
      yaxis: {
        fixedrange: true,
        tickformat: ".1%",
        rangemode: "tozero",
        title: { text: "share per day" },
      },
    }),
    CONFIG,
  );
}

const hline = (y) => ({
  type: "line",
  xref: "paper",
  x0: 0,
  x1: 1,
  y0: y,
  y1: y,
  line: { color: alpha(COLORS.ink, 0.35), width: 1, dash: "dot" },
});

function drawAll() {
  plotPieces();
  plotSeason();
}

watch(piecesVisible, drawAll);
watch(() => [seasonVisible.value, shapeYear.value], plotSeason);
watch(() => [props.data, locale.value], drawAll);
</script>
