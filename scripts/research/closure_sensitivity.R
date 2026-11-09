# Compare weather predictions with the explicit zero-passage closure assumption.
library(mgcv)
library(dplyr)
library(readr)
library(here)
source(here("scripts", "research", "hourly_uncertainty.R"))
set.seed(20261010)
args <- commandArgs(trailingOnly = TRUE)
output_dir <- if (length(args)) args[1] else here("logs", "hourly-weather-v2")
grid <- read_csv(here("archive", "hourly-weather", "prediction_hours.csv"), show_col_types = FALSE) |>
  filter(closure_exposure_hours > 0) |>
  mutate(exposure_hours = closure_exposure_hours, log_rain = log1p(rain_mm), log_previous_rain = log1p(rain_previous_24h_mm), radiation_100 = radiation_w_m2 / 100)
fits <- readRDS(file.path(output_dir, "model_fits.rds"))
support <- read_csv(file.path(output_dir, "weather_support_hours.csv"), show_col_types = FALSE) |>
  select(english_name, slot_start, sparse_weather_combination, outside_observed_range)
results <- list()

# Closure counts are unknown; neither scenario supplies observations to the fit.
for (species in names(fits)) {
  fit <- fits[[species]]$weather
  sample <- grid |> filter(english_name == species)
  sample$year_factor <- factor(sample$year, levels = levels(fit$model$year_factor))
  sample$day_id <- factor(levels(fit$model$day_id)[1], levels = levels(fit$model$day_id))
  X <- predict(fit, newdata = sample, type = "lpmatrix")
  day_smooth <- fit$smooth[[which(vapply(fit$smooth, function(x) x$label == "s(day_id)", logical(1)))]]
  X[, day_smooth$first.para:day_smooth$last.para] <- 0
  day_sd <- sqrt(fit$sig2 / fit$sp["s(day_id)"])
  variance <- rowSums((X %*% fit$rate_covariance) * X) + day_sd^2
  expected <- exp(as.numeric(X %*% coef(fit)) + log(sample$exposure_hours) + variance / 2)
  beta <- MASS::mvrnorm(N_DRAWS, coef(fit), fit$rate_covariance)
  eta <- X %*% t(beta) + log(sample$exposure_hours)
  dates <- unique(sample$date)
  day_draws <- matrix(rnorm(length(dates) * N_DRAWS, sd = day_sd), nrow = length(dates))
  eta <- eta + day_draws[match(sample$date, dates), , drop = FALSE]
  predictive <- matrix(rnbinom(length(eta), mu = exp(eta), size = fit$family$getTheta(TRUE)), nrow = nrow(sample))
  daily_draws <- rowsum(predictive, match(sample$date, dates), reorder = FALSE)
  result <- sample |>
    left_join(support, by = c("english_name", "slot_start")) |>
    mutate(expected = expected, unsupported_hours = exposure_hours * (sparse_weather_combination | outside_observed_range)) |>
    group_by(english_name, date) |>
    summarise(closure_hours = sum(exposure_hours), predicted = sum(expected), unsupported_hours = sum(unsupported_hours), .groups = "drop")
  index <- match(result$date, dates)
  result$q10 <- apply(daily_draws, 1, quantile, 0.1)[index]
  result$q90 <- apply(daily_draws, 1, quantile, 0.9)[index]
  result$assumed_zero_passage <- 0
  result$count_observed <- NA_real_
  results[[species]] <- result
}
write_csv(bind_rows(results), file.path(output_dir, "closure_sensitivity.csv"))
cat("Closure assumption sensitivity saved; closure counts remain unknown\n")
