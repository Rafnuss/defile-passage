# Load packages -------------------------------------------------------------
library(mgcv)
library(dplyr)
library(readr)
library(cli)

# Reuse training-only GAM bases; evaluate rates on canonical clock hours -----
args <- commandArgs(trailingOnly = TRUE)
input_dir <- args[1]
output_dir <- args[2]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
observations <- read_csv("data/mixed-weather-intervals/observations.csv", show_col_types = FALSE)
components <- read_csv("data/mixed-weather-intervals/hour_components.csv", show_col_types = FALSE) |>
  mutate(log_rain = log1p(rain_mm), log_previous_rain = log1p(rain_previous_24h_mm), radiation_100 = radiation_w_m2 / 100, exposure_hours = 1) |>
  left_join(observations |> select(observation_id, english_name), by = "observation_id")
manifest <- read_csv(file.path(input_dir, "manifest.csv"), show_col_types = FALSE) |> filter(fold == 4 | fold >= 5)
for (i in seq_len(nrow(manifest))) {
  key <- manifest$key[i]
  fit <- readRDS(file.path(input_dir, paste0(key, "_independent.rds")))
  rows <- components |> filter(english_name == manifest$english_name[i])
  rows$year_factor <- factor(rows$year, levels = if (manifest$fold[i] == 4) levels(fit$model$year_factor) else sort(unique(rows$year)))
  cli_alert_info("Preparing coherent hourly rates: {key}")
  write_csv(rows, file.path(output_dir, paste0(key, "_components.csv")))
  write_csv(observations |> filter(english_name == manifest$english_name[i]), file.path(output_dir, paste0(key, "_observations.csv")))
  write.table(predict(fit, rows, type = "lpmatrix"), file.path(output_dir, paste0(key, "_X.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  file.copy(file.path(input_dir, paste0(key, "_penalty.csv")), file.path(output_dir, paste0(key, "_penalty.csv")), overwrite = TRUE)
}
write_csv(manifest, file.path(output_dir, "manifest.csv"))

# Expose the time coefficients for refitting on actual mixed-scale coverage --
for (key in manifest$key) {
  fit <- readRDS(file.path(input_dir, paste0(key, "_independent.rds")))
  write_csv(tibble(index = seq_along(coef(fit)) - 1L, name = names(coef(fit)), time_effect = grepl("s\\(tau\\)|ti\\(tau,doy\\)", names(coef(fit)))), file.path(output_dir, paste0(key, "_coefficient_names.csv")))
}
