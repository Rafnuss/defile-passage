<template>
  <figure class="figure w-100">
    <div class="weather-effects-grid">
      <WeatherEffectPlot v-for="effect in weather.effects" :key="effect.term" :effect="effect" />
      <WeatherEffectPlot :effect="weather.wind" />
    </div>
    <figcaption class="figure-caption">
      <strong>Figure 2.5.</strong> {{ name }}: fitted weather multipliers and 95% intervals, with
      other terms held fixed. Wind combines three coefficients. Curves are calculated from the
      exported contrasts, including effects not selected for the public display.
    </figcaption>
  </figure>
</template>
<script setup>
import WeatherEffectPlot from "./WeatherEffectPlot.vue";
defineProps({ weather: { type: Object, required: true }, name: { type: String, required: true } });
</script>
