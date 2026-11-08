<template>
  <div>
    <section id="model-m-overview">
      <h5><span class="sec-n">1</span>The model in brief</h5>
      <p>
        For each species, we model the <strong>observed count</strong>&nbsp;<Tex e="N_d" />, the
        number of birds counted on day <Tex e="d" />, with a negative binomial distribution. Its
        mean, the <strong>expected observed count</strong>&nbsp;<Tex e="\mu_d" />, is the product of
        two quantities:
      </p>
      <div class="eq">
        <Tex
          display
          e="N_d \sim \operatorname{NegBin}(\mu_d,\ \theta), \qquad \mu_d = c_d\,R_d \tag{1}"
        />
      </div>
      <ul>
        <li>
          the <strong>coverage</strong>&nbsp;<Tex e="c_d" />, the proportion of the day’s expected
          passage that falls within the counting intervals. It is calculated before the model is
          fitted, from the counting times and the species’ time-of-day profile, and is treated as
          known (Section 2.2);
        </li>
        <li>
          the <strong>expected full-day passage</strong>&nbsp;<Tex e="R_d" />, the expected number
          of birds of the species passing over the whole day. This is what the model estimates.
        </li>
      </ul>
      <p>
        The dispersion parameter <Tex e="\theta" /> lets the counts vary more than a Poisson
        distribution would (Section 2.3). On the logarithmic scale, the expected full-day passage is
        the sum of a base level and six effects. For day <Tex e="d" />, <Tex e="y_d" /> denotes its
        year and <Tex e="t_d" /> its day of year:
      </p>
      <div class="eq">
        <Tex
          display
          e="\log R_d = \alpha + \Tr(y_d) + \Yr_{y_d} + \Se(t_d) + \Sh(y_d,t_d) + \Wx_d + \Ep_{y_d}(t_d) \tag{2}"
        />
      </div>
      <table class="terms">
        <tbody v-for="g in GROUPS" :key="g.name">
          <tr>
            <th colspan="3" class="terms-group">{{ g.name }}</th>
          </tr>
          <tr v-for="term in g.terms" :key="term.name">
            <td class="terms-sym"><Tex :e="term.tex" /></td>
            <th scope="row" :class="term.cls">{{ term.name }}</th>
            <td>
              <em>{{ term.form }}.</em> {{ term.text }}
            </td>
          </tr>
        </tbody>
      </table>
      <p>
        Because the effects are added on the logarithmic scale, they <em>multiply</em> the number of
        birds: an increase of 0.1 in any effect means about 10% more expected birds, holding the
        other effects fixed. Taking logarithms of eq. (1) gives
        <Tex e="\log\mu_d = \log c_d + \log R_d" />: the known <Tex e="\log c_d" /> enters the model
        as an <em>offset</em>, a term whose coefficient is fixed at one rather than estimated.
      </p>
      <p>
        This is a generalised additive model (GAM). We fit it by empirical Bayes inference: each
        effect has a Gaussian prior, which acts as a penalty that keeps curves smooth and effects
        small unless the counts support them, and the strength of each penalty is itself estimated
        from the counts (Sections 2.5 and 2.6).
      </p>
      <p>
        The rest of this chapter takes each part in turn: the coverage (Section 2.2), the negative
        binomial distribution (Section 2.3), the effects on expected full-day passage (Section 2.4),
        the penalties (Section 2.5) and the fitting (Section 2.6).
      </p>
    </section>
    <MethodCoverage :name="name" :data="data" :effort="effort" />
    <p v-if="!data.trend" class="callout callout-info">
      {{ name }} has no fitted daily count model. Its coverage is still available above; choose a
      species such as Red Kite to see the model illustrations.
    </p>
    <template v-if="data.trend">
      <section id="model-m-scatter">
        <h5><span class="sec-n">3</span>Variation of the counts around their expectation</h5>
        <p>
          The expected observed count <Tex e="\mu_d" /> is an average: the observed counts
          <Tex e="N_d" /> vary around it from day to day, and the distribution in eq. (1) describes
          this variation. If birds passed independently of one another, <Tex e="N_d" /> would follow
          a <strong>Poisson</strong> distribution, whose variance equals its mean. Real counts vary
          more, because birds may travel in flocks and because days differ in ways that the model
          cannot fully explain. The <strong>negative binomial</strong> distribution allows for this
          extra variation through its dispersion parameter <Tex e="\theta" />:
        </p>
        <div class="eq">
          <Tex display e="\operatorname{Var}(N_d) = \mu_d + \frac{\mu_d^2}{\theta} \tag{4}" />
        </div>
        <p>
          The second term, <Tex e="\mu_d^2/\theta" />, is the variance in excess of that of a
          Poisson distribution. A small value of <Tex e="\theta" /> allows much greater variation
          between days; as the value of <Tex e="\theta" /> grows, the distribution approaches a
          Poisson with the same mean <Tex e="\mu_d" />. Each species has a single value of
          <Tex e="\theta" />, estimated together with the smoothing parameters (Section 2.6).
        </p>
        <NegBinWidget :name="name" :species-theta="trend.theta" />
      </section>
      <section id="model-m-model">
        <h5><span class="sec-n">4</span>Effects on expected full-day passage</h5>
        <p>
          This section describes the effects in eq. (2) by time scale: over the years (trend and
          year level), over the season (season and change of timing) and from day to day (weather
          and episodes).
        </p>

        <h6 class="model-timescale">Over the years</h6>
        <p>
          The <strong class="t-trend">trend</strong>&nbsp;<Tex e="\Tr(y)" /> describes gradual
          change in passage across years, and the
          <strong class="t-year">year level</strong>&nbsp;<Tex e="\Yr_y" /> each year’s departure
          from it. On its own, the trend is not a change in the number of birds: it is defined on
          the logarithmic scale with every day of the season weighted equally, and it interacts with
          the change of timing. Figure 2.3 therefore summarises these effects as season totals, in
          birds.
        </p>
        <figure class="figure w-100">
          <div class="row g-2">
            <div class="col-md-6">
              <div class="panel-title t-trend">
                a. Smooth season total · <Tex e="\alpha+\Tr+\Se+\Sh" />
              </div>
              <div ref="trendDiv" class="plot-sm"></div>
            </div>
            <div class="col-md-6">
              <div class="panel-title t-year">
                b. Season total / smooth season total · <Tex e="\Yr,\Wx,\Ep" />
              </div>
              <div ref="yearDiv" class="plot-sm"></div>
            </div>
          </div>
          <figcaption class="figure-caption">
            <strong>Figure 2.3.</strong> Summaries of the fitted model for {{ name }}.
            <strong>a.</strong> The smooth season total: the expected full-day passage summed over
            the season, from the base level <Tex e="\alpha" /> together with the effects of the
            trend <Tex e="\Tr" />, the season <Tex e="\Se" /> and the change of timing
            <Tex e="\Sh" />, in a typical year (the effects of year level, weather and episodes at
            their average). It is shown relative to {{ trend.first_year }}, with its 95% interval.
            <strong>b.</strong> Each year’s reconstructed total divided by its smooth season total:
            the departure due to the effects of that year’s level, weather and episodes. Values
            above 1 indicate more passage than the smooth expectation.
          </figcaption>
        </figure>
        <h6 class="model-timescale">Over the season</h6>
        <p id="model-m-timing">
          The <strong class="t-season">season</strong>&nbsp;<Tex e="\Se(t)" /> is the average shape
          of the season, shared by all years: when the species passes, and how spread out its
          passage is. The <strong class="t-shift">change of timing</strong>&nbsp;<Tex
            e="\Sh(y,t)"
          />
          describes gradual departures from that shape over the decades. Such changes occur when
          populations alter the timing of their migration, or when populations passing at different
          times change in relative abundance.
        </p>
        <p>
          <Tex e="\Sh(y,t)" /> is a smooth function of both year and day of year, so it captures
          only slow changes. The short-lived peaks and gaps of individual seasons are described by
          the effects of weather and episodes instead.
        </p>
        <figure class="figure w-100">
          <label for="shape-year" class="form-label"
            >Seasonal shape · <Tex e="\Se(t)+\Sh(y,t)" /> · <strong>{{ shapeYear }}</strong></label
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
            references. Each curve integrates to one; the effects of weather and episodes are
            omitted.
          </figcaption>
        </figure>
        <h6 id="model-m-days" class="model-timescale">From day to day</h6>
        <p id="model-m-weather">
          The <strong class="t-weather">weather</strong> effect <Tex e="\Wx_d" /> is a linear
          combination of nine daily weather variables <Tex e="w_{j,d}" />, each standardised:
        </p>
        <div class="eq"><Tex display e="\Wx_d = \sum_{j=1}^{9}\beta_j w_{j,d}" /></div>
        <p>
          The coefficient <Tex e="\beta_j" /> gives how much variable <Tex e="j" /> changes the log
          expected full-day passage, holding the other effects fixed. The variables are calculated
          from hourly
          <a href="https://open-meteo.com/en/docs/historical-weather-api"
            >ERA5 reanalysis data from the Open-Meteo archive</a
          >
          at the Défilé (0.25° grid), in four steps:
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
                <strong>Wind speed, <Tex e="s" />:</strong>&nbsp;<a
                  href="https://open-meteo.com/en/docs/historical-weather-api"
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
        <WeatherPanels v-if="data.weather" :weather="data.weather" :name="name" />
        <p>
          The <strong class="t-episode">episode</strong> effect <Tex e="\Ep_y(t)" /> is a smooth
          curve along the day of year, separate for each year. It describes runs of unusually busy
          or quiet days that the other effects do not explain. These runs may reflect weather
          elsewhere along the route, the arrival of particular populations, social behaviour or
          other processes; the model does not identify their cause.
        </p>
        <p>
          Because the episode curve is smooth, the counts on the days before and after a gap
          constrain it during the gap, which helps to reconstruct short gaps. This is particularly
          useful with the near-continuous counting at the Défilé. Across a long gap, the counts give
          much less information about where a run of busy days occurred.
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
        <h5><span class="sec-n">5</span>Penalties: how smooth is smooth?</h5>
        <p>
          Each smooth effect (<Tex e="\Tr" />, <Tex e="\Se" />, <Tex e="\Sh" />, <Tex e="\Ep" />) is
          a <em>spline</em>: a weighted sum of fixed, smoothly joined polynomial pieces, flexible
          enough to follow almost any shape. Too flexible, a curve would follow random fluctuations
          in the counts. A penalty on its wiggliness prevents this: for given smoothing parameters,
          the coefficients maximise the penalised log-likelihood
        </p>
        <div class="eq">
          <Tex
            display
            e="\text{log-likelihood of the counts} \;-\; \sum_k \rho_k \times \text{wiggliness}_k \tag{5}"
          />
        </div>
        <p>
          The wiggliness measures how much a curve bends. A large smoothing parameter
          <Tex e="\rho_k" /> favours a simpler curve; a small one lets it bend more. The smoothing
          parameters are estimated from the counts, together with <Tex e="\theta" /> (Section 2.6).
        </p>
        <p>
          The other effects are penalised for their size rather than their wiggliness. The year
          levels <Tex e="\Yr_y" /> have a penalty whose strength is also estimated, which makes them
          a random effect. The weather coefficients <Tex e="\beta_j" /> have a fixed penalty:
          without a clear signal in the counts, a weather effect stays near zero.
        </p>
        <SmoothWidget :name="name" :annual="trend.annual" />
      </section>
      <section id="model-m-fit">
        <h5><span class="sec-n">6</span>Fitting the model</h5>
        <p>
          We fit the model by empirical Bayes inference, as is standard for generalised additive
          models (Wood 2011, 2017). The penalties of Section 2.5 are Gaussian priors on the
          coefficients. Two groups of parameters are estimated:
        </p>
        <ul>
          <li>
            the <strong>coefficients</strong>, which determine the level, the shape of the curves
            and the size of the year levels and weather effects, and hence the expected full-day
            passage on each day;
          </li>
          <li>
            the <strong>hyperparameters</strong>: the smoothing parameters <Tex e="\rho_k" />, which
            set the strength of the penalties, and the dispersion parameter <Tex e="\theta" /> of
            the negative binomial distribution (eq. 1).
          </li>
        </ul>
        <p>
          With the hyperparameters fixed, the coefficients are estimated by penalised iteratively
          reweighted least squares, which finds the posterior mode: the coefficients that maximise
          the negative-binomial log-likelihood of the counts minus the penalties (eq. 5). The
          hyperparameters are estimated by maximising the marginal likelihood of the counts, which
          integrates over the uncertainty in the coefficients; we use its Laplace approximation. The
          fitting alternates between the two:
        </p>
        <ol>
          <li><strong>Estimate the coefficients</strong> with the hyperparameters fixed.</li>
          <li><strong>Update the hyperparameters</strong> with the coefficients from step 1.</li>
          <li>
            <strong>Repeat</strong> until the changes are small or the iteration limits are reached.
          </li>
        </ol>
        <p>
          After fitting, the uncertainty in the coefficients is described by a multivariate Gaussian
          approximation of their posterior distribution, with the hyperparameters treated as fixed.
          Draws from it give plausible combinations of the effects, which the reconstruction of full
          days (Chapter 3) uses to draw the birds missed outside the counting intervals.
        </p>
        <p>
          Only days with a coverage of at least {{ Math.round(100 * trend.min_coverage) }}% (<Tex
            :e="`c_d\\ge${trend.min_coverage}`"
          />) enter the fit. This avoids estimating the full-day passage from very short counts that
          may happen to contain a single flock.
        </p>
        <details class="method-detail">
          <summary>Solver details</summary>
          <p>
            The implementation uses Python with
            <a href="https://numpy.org/doc/stable/">NumPy</a> for arrays and
            <a href="https://docs.scipy.org/doc/scipy/">SciPy</a> for splines, linear algebra and
            optimisation.
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
              <strong>Smoothing and dispersion.</strong> Extended Fellner–Schall updates (Wood and
              Fasiolo 2017) estimate the smoothing penalties. Bounded scalar optimisation updates
              the same <Tex e="\theta" /> used in the negative binomial, alternating with smoothing
              updates under a Laplace-approximated marginal likelihood.
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
        <p class="small">
          <strong>References.</strong><br />
          Wood, S. N. (2011). Fast stable restricted maximum likelihood and marginal likelihood
          estimation of semiparametric generalized linear models. <em>JRSS B</em> 73: 3–36.<br />
          Wood, S. N. (2017). <em>Generalized Additive Models: An Introduction with R</em>, 2nd ed.
          Chapman &amp; Hall/CRC.<br />
          Wood, S. N. and Fasiolo, M. (2017). A generalized Fellner–Schall method for smoothing
          parameter optimization with application to Tweedie location, scale and shape models.
          <em>Biometrics</em> 73: 1071–1081.
        </p>
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

// The terms of eq. (2), in the order of the equation, by time scale
const GROUPS = [
  {
    name: "Over the years",
    terms: [
      {
        tex: "\\alpha",
        name: "base level",
        cls: "",
        form: "Constant",
        text: "The base level of the log expected full-day passage, around which the other effects raise or lower passage.",
      },
      {
        tex: "\\Tr(y)",
        name: "trend",
        cls: "t-trend",
        form: "Smooth function of year (penalised spline)",
        text: "Gradual change across years, generally associated with long-term population change, but possibly also with shifts in migration routes or in visibility at the site.",
      },
      {
        tex: "\\Yr_y",
        name: "year level",
        cls: "t-year",
        form: "One value per year (random effect)",
        text: "Each year’s departure from the trend: good and bad years, for example because of breeding success or a shifted route.",
      },
    ],
  },
  {
    name: "Over the season",
    terms: [
      {
        tex: "\\Se(t)",
        name: "season",
        cls: "t-season",
        form: "Smooth function of day of year (penalised spline)",
        text: "The average shape of the season: when the species passes, and how spread out its passage is.",
      },
      {
        tex: "\\Sh(y,t)",
        name: "change of timing",
        cls: "t-shift",
        form: "Smooth function of year and day of year (penalised spline)",
        text: "Gradual change of that shape over the decades, for example a season starting earlier or lasting longer.",
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
        form: "Linear in nine weather variables (fixed effects with a shrinkage prior)",
        text: "The effect of the day’s weather: rain, sunshine, thermal mixing, wind, pressure change and temperature (Section 2.4).",
      },
      {
        tex: "\\Ep_y(t)",
        name: "episodes",
        cls: "t-episode",
        form: "Smooth function of day of year, separate for each year (penalised spline)",
        text: "Runs of a few busy or quiet days that the other effects do not explain (Section 2.4).",
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
