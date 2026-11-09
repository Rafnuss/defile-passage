# Load packages -------------------------------------------------------------
library(mgcv)
library(dplyr)
library(tidyr)
library(readr)
library(ggplot2)
library(here)
library(cli)
set.seed(20261010)
source(here("scripts", "research", "hourly_uncertainty.R"))

# Read data -----------------------------------------------------------------
# Run from defile-passage; arguments optionally override input and output folders.
args <- commandArgs(trailingOnly = TRUE)
input_dir <- if (length(args) >= 1) args[1] else here("data", "hourly-weather")
output_dir <- if (length(args) >= 2) args[2] else here("logs", "hourly-weather-v2")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
frame <- read_csv(file.path(input_dir, "model_frame.csv"), show_col_types = FALSE)
eligibility <- frame |>
  group_by(english_name, year) |>
  summarise(intervals = n(), eligible = sum(model_eligible), eligible_birds = sum(count[model_eligible]), unknown_hours = sum(!hourly_complete), outside_daylight = sum(!within_daylight), missing_weather = sum(!weather_available), .groups = "drop")
write_csv(eligibility, file.path(output_dir, "eligibility.csv"))
data <- read_csv(file.path(input_dir, "validation_masks.csv"), show_col_types = FALSE) |>
  mutate(year_factor = factor(year), day_id = factor(date), log_rain = log1p(rain_mm), log_previous_rain = log1p(rain_previous_24h_mm), radiation_100 = radiation_w_m2 / 100) |>
  arrange(english_name, date, start)

# Specify comparable count-rate models --------------------------------------
# Day effects share information across a day's hours; they are independent between days.
# Four recent years estimate year levels, not a long-term trend or phenology shift.
formulas <- list(
  baseline = count ~ year_factor + s(doy, k = 18) + s(tau, k = 10) + ti(tau, doy, k = c(6, 8)) + s(day_id, bs = "re") + offset(log(exposure_hours)),
  weather = count ~ year_factor + s(doy, k = 18) + s(tau, k = 10) + ti(tau, doy, k = c(6, 8)) + s(log_rain, k = 6) + s(log_previous_rain, k = 6) + s(wind_u_m_s, k = 6) + s(wind_v_m_s, k = 6) + s(radiation_100, k = 6) + s(low_cloud_fraction, k = 6) + s(day_id, bs = "re") + offset(log(exposure_hours))
)
# Test flexibility and weather simplification separately; validation selects neither automatically.
formulas$weather_time <- update(formulas$weather, . ~ . - s(doy, k = 18) - s(tau, k = 10) - ti(tau, doy, k = c(6, 8)) + s(doy, k = 30) + s(tau, k = 16) + ti(tau, doy, k = c(10, 12)))
formulas$weather_reduced <- update(formulas$weather, . ~ . - s(radiation_100, k = 6) - s(low_cloud_fraction, k = 6))
n_draws <- N_DRAWS
fits <- list()
hour_results <- list()
day_results <- list()
diagnostics <- list()
rain_curves <- list()
sensitivity <- list()
basis_diagnostics <- list()
concurvity_diagnostics <- list()

# Fit each species and test contiguous gaps ----------------------------------
for (species in unique(data$english_name)) {
  cli_alert_info("Fitting {species}")
  species_data <- data |> filter(english_name == species)
  # Three seven-day block folds; every eligible interval is held out once.
  # A fourth fold hides up to three adjacent hours around the wettest hour, or midday on dry days.
  masks <- species_data
  for (fold in 0:3) {
    hidden <- if (fold == 3) masks$hidden_hours else masks$block_fold == fold
    training <- species_data[!hidden, ] |> mutate(day_id = droplevels(day_id))
    testing <- species_data[hidden, ]
    # Placeholder only for evaluating the design matrix; unseen day columns are zeroed below.
    unseen <- !as.character(testing$day_id) %in% levels(training$day_id)
    testing$day_id <- factor(ifelse(unseen, levels(training$day_id)[1], as.character(testing$day_id)), levels = levels(training$day_id))
    for (variant in names(formulas)) {
      cli_alert_info("  {variant}, fold {fold + 1}/4")
      fit <- bam(formulas[[variant]], data = training, family = nb(), method = "fREML", discrete = TRUE, select = TRUE, nthreads = 1)
      saveRDS(fit, file.path(output_dir, paste0(gsub(" ", "_", species), "_", variant, "_fold", fold, ".rds")))
      X <- predict(fit, newdata = testing, type = "lpmatrix")
      day_smooth <- fit$smooth[[which(vapply(fit$smooth, function(x) x$label == "s(day_id)", logical(1)))]]
      X[unseen, day_smooth$first.para:day_smooth$last.para] <- 0
      covariance <- rate_covariance(fit, training)
      beta <- MASS::mvrnorm(n_draws, coef(fit), covariance)
      eta <- X %*% t(beta) + log(testing$exposure_hours)
      day_sd <- sqrt(fit$sig2 / fit$sp["s(day_id)"])
      if (any(unseen)) {
        new_days <- unique(testing$date[unseen])
        # One latent effect per unseen day per draw, shared by all that day's hidden hours.
        day_draws <- matrix(rnorm(length(new_days) * n_draws, sd = day_sd), nrow = length(new_days))
        eta[unseen, ] <- eta[unseen, , drop = FALSE] + day_draws[match(testing$date[unseen], new_days), , drop = FALSE]
      }
      mean_draws <- exp(eta)
      # Analytic log-normal mean avoids a few Monte Carlo draws deciding a gap total.
      log_variance <- rowSums((X %*% covariance) * X) + unseen * day_sd^2
      expected <- exp(as.numeric(X %*% coef(fit)) + log(testing$exposure_hours) + log_variance / 2)
      for (floor in RATE_FLOORS) {
        V <- if (floor == MIN_DAILY_RATE) covariance else rate_covariance(fit, training, floor)
        variance <- rowSums((X %*% V) * X) + unseen * day_sd^2
        sensitivity[[length(sensitivity) + 1]] <- testing |>
          select(english_name, date, count, rain_mm) |>
          mutate(model = variant, fold = fold, gap = ifelse(fold == 3, "hours", "days"), daily_rate_floor = floor, predicted = exp(as.numeric(X %*% coef(fit)) + log(testing$exposure_hours) + variance / 2), log_rate_sd = sqrt(variance))
      }
      predictive <- matrix(rnbinom(length(mean_draws), mu = mean_draws, size = fit$family$getTheta(TRUE)), nrow = nrow(testing))
      log_density <- matrix(dnbinom(testing$count, mu = mean_draws, size = fit$family$getTheta(TRUE), log = TRUE), nrow = nrow(testing))
      max_log <- apply(log_density, 1, max)
      result <- testing |>
        select(english_name, survey_id, date, year, slot_start, start, end, exposure_hours, count, rain_mm, rain_previous_24h_mm) |>
        mutate(model = variant, fold = fold, gap = ifelse(fold == 3, "hours", "days"), predicted = expected, median_rate_count = exp(as.numeric(X %*% coef(fit)) + log(exposure_hours)), log_rate_sd = sqrt(log_variance), q025 = apply(predictive, 1, quantile, 0.025), q10 = apply(predictive, 1, quantile, 0.1), q90 = apply(predictive, 1, quantile, 0.9), q975 = apply(predictive, 1, quantile, 0.975), log_score = max_log + log(rowMeans(exp(log_density - max_log))))
      hour_results[[length(hour_results) + 1]] <- result
      # Aggregate the same draws to retain parameter and shared-day dependence.
      group <- match(testing$date, unique(testing$date))
      daily_draws <- rowsum(predictive, group, reorder = FALSE)
      daily_means <- rowsum(expected, group, reorder = FALSE)
      daily <- result |>
        group_by(date) |>
        summarise(english_name = first(english_name), year = first(year), model = first(model), fold = first(fold), gap = first(gap), count = sum(count), hours = sum(exposure_hours), rain_mm = sum(rain_mm * exposure_hours), .groups = "drop")
      index <- match(daily$date, unique(testing$date))
      daily$predicted <- daily_means[index, 1]
      daily$q025 <- apply(daily_draws, 1, quantile, 0.025)[index]
      daily$q10 <- apply(daily_draws, 1, quantile, 0.1)[index]
      daily$q90 <- apply(daily_draws, 1, quantile, 0.9)[index]
      daily$q975 <- apply(daily_draws, 1, quantile, 0.975)[index]
      day_results[[length(day_results) + 1]] <- daily
    }
  }
  # Final fits are saved for inspection; validation above never uses these fits.
  fits[[species]] <- list()
  for (variant in names(formulas)) {
    cli_alert_info("  {variant}, final fit")
    fit <- bam(formulas[[variant]], data = species_data, family = nb(), method = "fREML", discrete = TRUE, select = TRUE, nthreads = 1)
    fits[[species]][[variant]] <- fit
    fits[[species]][[variant]]$rate_covariance <- rate_covariance(fit, species_data)
    basis_diagnostics[[length(basis_diagnostics) + 1]] <- as_tibble(k.check(fit), rownames = "term") |> mutate(english_name = species, model = variant)
    concurvity_diagnostics[[length(concurvity_diagnostics) + 1]] <- as_tibble(t(concurvity(fit, full = TRUE)), rownames = "term") |> mutate(english_name = species, model = variant)
    residual <- residuals(fit, type = "pearson")
    adjacent <- diff(as.numeric(species_data$slot_start)) == 3600 & head(species_data$date, -1) == tail(species_data$date, -1)
    diagnostics[[length(diagnostics) + 1]] <- tibble(english_name = species, model = variant, theta = fit$family$getTheta(TRUE), day_sd = sqrt(fit$sig2 / fit$sp["s(day_id)"]), deviance_explained = summary(fit)$dev.expl, neighboring_residual_correlation = cor(head(residual, -1)[adjacent], tail(residual, -1)[adjacent]))
    sink(file.path(output_dir, paste0(gsub(" ", "_", species), "_", variant, "_diagnostics.txt")))
    print(summary(fit))
    print(concurvity(fit, full = TRUE))
    print(k.check(fit))
    sink()
    # Verify that the fitted response remains a count with exposure in real hours.
    check <- species_data[1:2, ]
    check[2, ] <- check[1, ]
    check$exposure_hours <- c(0.5, 1)
    stopifnot(abs(diff(log(predict(fit, check, type = "response"))) - log(2)) < 1e-8)
  }
  # Partial precipitation effect, with the remaining predictors held fixed.
  fit <- fits[[species]]$weather
  rain <- seq(0, quantile(species_data$rain_mm, 0.995), length.out = 100)
  reference <- species_data[rep(1, length(rain)), ]
  reference$log_rain <- log1p(rain)
  X <- predict(fit, reference, type = "lpmatrix")
  difference <- sweep(X, 2, X[1, ], "-")
  effect <- as.numeric(difference %*% coef(fit))
  se <- sqrt(rowSums((difference %*% fit$rate_covariance) * difference))
  rain_curves[[species]] <- tibble(english_name = species, rain_mm = rain, multiplier = exp(effect), lo = exp(effect - 1.96 * se), hi = exp(effect + 1.96 * se))
}

# Summarise predictive performance ------------------------------------------
hours <- bind_rows(hour_results) |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry"))
days <- bind_rows(day_results) |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry"))
hour_scores <- hours |>
  group_by(english_name, model, gap, weather_group) |>
  summarise(intervals = n(), mae = mean(abs(predicted - count)), mean_log_score = mean(log_score), cover80 = mean(count >= q10 & count <= q90), cover95 = mean(count >= q025 & count <= q975), counted = sum(count), predicted = sum(predicted), .groups = "drop")
day_scores <- days |>
  group_by(english_name, model, gap, weather_group) |>
  summarise(days = n(), mae = mean(abs(predicted - count)), cover80 = mean(count >= q10 & count <= q90), cover95 = mean(count >= q025 & count <= q975), counted = sum(count), predicted = sum(predicted), .groups = "drop") |>
  mutate(bias_fraction = predicted / counted - 1)
write_csv(hours, file.path(output_dir, "held_out_hours.csv"))
write_csv(days, file.path(output_dir, "held_out_days.csv"))
write_csv(hour_scores, file.path(output_dir, "hour_scores.csv"))
write_csv(day_scores, file.path(output_dir, "day_scores.csv"))
write_csv(bind_rows(diagnostics), file.path(output_dir, "diagnostics.csv"))
write_csv(bind_rows(rain_curves), file.path(output_dir, "rain_effects.csv"))
write_csv(bind_rows(basis_diagnostics), file.path(output_dir, "basis_checks.csv"))
write_csv(bind_rows(concurvity_diagnostics), file.path(output_dir, "concurvity.csv"))
floor_scores <- bind_rows(sensitivity) |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry")) |>
  group_by(english_name, model, gap, daily_rate_floor, weather_group) |>
  summarise(mae = mean(abs(predicted - count)), counted = sum(count), predicted = sum(predicted), maximum_log_rate_sd = max(log_rate_sd), .groups = "drop") |>
  mutate(bias_fraction = predicted / counted - 1)
write_csv(floor_scores, file.path(output_dir, "floor_sensitivity.csv"))
write_lines(read_lines(file.path(input_dir, "metadata.json")), file.path(output_dir, "data_snapshot.json"))
saveRDS(fits, file.path(output_dir, "model_fits.rds"))
capture.output(sessionInfo(), file = file.path(output_dir, "sessionInfo.txt"))

# Plotting ------------------------------------------------------------------
rain_plot <- ggplot(bind_rows(rain_curves), aes(rain_mm, multiplier)) +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.15) + geom_line() +
  geom_hline(yintercept = 1, linetype = "dotted") + facet_wrap(vars(english_name), scales = "free") +
  labs(x = "Precipitation during the hour (mm)", y = "Rate relative to a dry hour", subtitle = "Partial GAM effect; other weather held fixed; 95% coefficient intervals") + theme_bw()
ggsave(file.path(output_dir, "rain_effects.png"), rain_plot, width = 10, height = 7, dpi = 180)
comparison_plot <- ggplot(hour_scores |> filter(gap == "days"), aes(weather_group, mean_log_score, fill = model)) +
  geom_col(position = "dodge") + facet_wrap(vars(english_name), scales = "free_y") +
  labs(x = "Weather during held-out observed intervals", y = "Mean hourly log predictive density (higher is better)", subtitle = "Seven-day blocks withheld; genuinely observed counts, including zeros", fill = "Model") + theme_bw()
ggsave(file.path(output_dir, "blocked_comparison.png"), comparison_plot, width = 10, height = 7, dpi = 180)
print(day_scores, n = Inf)
cli_alert_success("Hourly pilot and blocked validation saved to {output_dir}")
