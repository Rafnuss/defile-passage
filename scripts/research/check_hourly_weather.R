# Load packages and completed outputs ---------------------------------------
library(mgcv)
library(dplyr)
library(readr)
library(here)
source(here("scripts", "research", "hourly_uncertainty.R"))
set.seed(20261010)
args <- commandArgs(trailingOnly = TRUE)
output_dir <- if (length(args)) args[1] else here("logs", "hourly-weather-v2")
data <- read_csv(here("data", "hourly-weather", "validation_masks.csv"), show_col_types = FALSE) |>
  mutate(year_factor = factor(year), day_id = factor(date), log_rain = log1p(rain_mm), log_previous_rain = log1p(rain_previous_24h_mm), radiation_100 = radiation_w_m2 / 100)

# Regression: observed zero tails cannot imply enormous Gaussian rate variance.
probe <- tibble(doy = 1:150, count = c(rep(0, 50), rpois(50, 20), rep(0, 50)), exposure_hours = 1, dawn = as.POSIXct("2025-09-01 06:00:00", tz = "UTC"), dusk = as.POSIXct("2025-09-01 18:00:00", tz = "UTC"))
fit <- gam(count ~ s(doy, k = 18) + offset(log(exposure_hours)), data = probe, family = nb(), method = "REML", select = TRUE)
X <- predict(fit, type = "lpmatrix")
V <- rate_covariance(fit, probe)
raw_variance <- rowSums((X %*% fit$Vp) * X)
variance <- rowSums((X %*% V) * X)
stopifnot(max(variance) < max(raw_variance), all(variance <= raw_variance + 1e-6))
stopifnot(max(abs(rate_covariance(fit, probe, 0) - fit$Vp)) < 1e-5)
expected <- exp(fit$linear.predictors + variance / 2)
stopifnot(all(is.finite(expected)), max(expected[probe$count == 0]) < 100)
cat("Zero-tail uncertainty regression passed\n")

# Verify actual masks, aggregation and fitted exposure -----------------------
hours <- read_csv(file.path(output_dir, "held_out_hours.csv"), show_col_types = FALSE)
days <- read_csv(file.path(output_dir, "held_out_days.csv"), show_col_types = FALSE)
stopifnot(all(is.finite(hours$predicted)), all(hours$predicted >= 0), all(hours$q025 <= hours$q975))
reconciled <- hours |>
  group_by(english_name, model, fold, date) |>
  summarise(count = sum(count), predicted = sum(predicted), .groups = "drop") |>
  inner_join(days, by = c("english_name", "model", "fold", "date"), suffix = c("_hours", "_day"))
stopifnot(nrow(reconciled) == nrow(days), all(reconciled$count_hours == reconciled$count_day))
stopifnot(max(abs(reconciled$predicted_hours - reconciled$predicted_day)) < 1e-6)
fits <- readRDS(file.path(output_dir, "model_fits.rds"))
for (species in names(fits)) {
  sample <- data |> filter(english_name == species)
  for (variant in names(fits[[species]])) {
    fit <- fits[[species]][[variant]]
    check <- sample[rep(1, 2), ]
    check$exposure_hours <- c(0.5, 1)
    stopifnot(abs(diff(log(predict(fit, check, type = "response"))) - log(2)) < 1e-8)
  }
}
recomputed <- days |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry")) |>
  group_by(english_name, model, gap, weather_group) |>
  summarise(mae = mean(abs(predicted - count)), .groups = "drop") |>
  inner_join(read_csv(file.path(output_dir, "day_scores.csv"), show_col_types = FALSE), by = c("english_name", "model", "gap", "weather_group"), suffix = c("_check", "_saved"))
stopifnot(max(abs(recomputed$mae_check - recomputed$mae_saved)) < 1e-6)
cat("Saved fits, real-hour scaling, count conservation and score checks passed\n")
