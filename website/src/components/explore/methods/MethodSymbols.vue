<template>
  <section id="symbols" class="chapter">
    <header class="chapter-head">
      <h2>Symbols</h2>
      <p>Every symbol of the guide, in the order it appears.</p>
    </header>
    <table class="table table-sm small symbols">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Meaning</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in SYMBOLS" :key="row.tex">
          <td><Tex :e="row.tex" /></td>
          <td>{{ row.text }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import Tex from "../Tex.vue";

const SYMBOLS = [
  { tex: "d,\\ y_d,\\ s_d", text: "A day, its year and its day of year" },
  { tex: "N_d", text: "Observed daily count: birds recorded in the day's counting" },
  { tex: "t", text: "Time of day" },
  {
    tex: "p_d(t)",
    text: "Time-of-day profile: proportion of the day's passage at time t",
  },
  { tex: "c_d", text: "Coverage: proportion of the day's passage that was counted" },
  { tex: "R_d", text: "Expected full-day passage" },
  { tex: "\\mu_d", text: "Expected observed count, c_d R_d" },
  { tex: "\\theta", text: "Dispersion between days (negative binomial)" },
  { tex: "\\alpha", text: "Base level of the expected full-day passage" },
  {
    tex: "\\Tr,\\ \\Yr,\\ \\Se,\\ \\Sh",
    text: "Trend, year level, season, change of timing",
  },
  { tex: "\\Wx_d", text: "Effect of the day's weather" },
  {
    tex: "w_{j,d},\\ \\beta_j",
    text: "Weather variable j on day d, and its coefficient",
  },
  { tex: "\\Ep_y", text: "Episodes: runs of busy or quiet days in year y" },
  { tex: "\\rho_k", text: "Smoothing parameter of penalty k" },
  { tex: "F_d", text: "Full-day total: birds that passed on day d" },
  { tex: "M_d", text: "Missing birds: those not counted on day d" },
  { tex: "\\lambda_d", text: "Intensity: how busy day d is, in birds per full day" },
  { tex: "w_d", text: "Weight of the counted part in the updated intensity" },
  { tex: "m_d", text: "Expected missing birds given the intensity" },
  { tex: "\\kappa", text: "Dispersion within the day: flocks" },
  {
    tex: "b,\\ a_{d,b},\\ n_{d,b}",
    text: "A time block of the day, its expected share, its birds",
  },
];
</script>

<style scoped>
.symbols td:first-child {
  white-space: nowrap;
}
</style>
