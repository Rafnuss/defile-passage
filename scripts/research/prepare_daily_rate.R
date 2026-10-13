# Load packages -------------------------------------------------------------
library(mgcv)
library(dplyr)
library(readr)
library(here)
library(cli)
source(here("scripts", "research", "hourly_uncertainty.R"))
set.seed(20261010)

# Prepare matched masks and population rate bases ---------------------------
args <- commandArgs(trailingOnly = TRUE)
input_dir <- if (length(args) >= 1) args[1] else here("data", "hourly-weather")
output_dir <- if (length(args) >= 2) args[2] else here("logs", "hourly-weather-v3")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
file.copy(file.path(input_dir, "metadata.json"), file.path(output_dir, "data_snapshot.json"), overwrite = TRUE)
file.copy(file.path(input_dir, "recording_scope.tsv"), file.path(output_dir, "recording_scope.tsv"), overwrite = TRUE)
data <- read_csv(file.path(input_dir, "validation_masks.csv"), show_col_types = FALSE) |>
  mutate(year_factor = factor(year), log_rain = log1p(rain_mm), log_previous_rain = log1p(rain_previous_24h_mm), radiation_100 = radiation_w_m2 / 100) |>
  arrange(english_name, date, start)
formula <- count ~ year_factor + s(doy, k = 18) + s(tau, k = 10) + ti(tau, doy, k = c(6, 8)) + s(log_rain, k = 6) + s(log_previous_rain, k = 6) + s(wind_u_m_s, k = 6) + s(wind_v_m_s, k = 6) + s(radiation_100, k = 6) + s(low_cloud_fraction, k = 6) + offset(log(exposure_hours))
year_holdout <- length(args) >= 3 && args[3] == "year_holdout"
year_formula <- update(formula, . ~ . - year_factor)
manifest <- list()
for (species in unique(data$english_name)) {
  rows <- data |> filter(english_name == species)
  folds <- if (year_holdout) 5:(4 + n_distinct(rows$year)) else 0:4
  for (fold in folds) {
    heldout_year <- if (fold >= 5) sort(unique(rows$year))[fold - 4] else NA_integer_
    hidden <- if (fold == 4) rep(FALSE, nrow(rows)) else if (fold >= 5) rows$year == heldout_year else if (fold == 3) rows$hidden_hours else rows$block_fold == fold
    training <- rows[!hidden, ]
    testing <- if (fold == 4) rows else rows[hidden, ]
    key <- paste0(gsub(" ", "_", species), "_fold", fold)
    cli_alert_info("Preparing {key}")
    fit_formula <- if (fold >= 5) year_formula else formula
    fit <- bam(fit_formula, data = training, family = nb(), method = "fREML", discrete = TRUE, select = TRUE, nthreads = 1)
    X <- predict(fit, training, type = "lpmatrix")
    penalty <- matrix(0, ncol(X), ncol(X))
    components <- list()
    for (smooth in fit$smooth) {
      index <- smooth$first.para:smooth$last.para
      for (j in seq_along(smooth$S)) {
        component <- matrix(0, ncol(X), ncol(X))
        component[index, index] <- fit$sp[smooth$first.sp + j - 1] * smooth$S[[j]]
        penalty <- penalty + component
        components[[length(components) + 1]] <- component
      }
    }
    for (j in seq_along(components)) write.table(components[[j]], file.path(output_dir, paste0(key, "_S", j, ".csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write_csv(tibble(component = seq_along(components), name = names(fit$sp), initial_sp = as.numeric(fit$sp)), file.path(output_dir, paste0(key, "_smoothing.csv")))
    write_csv(training, file.path(output_dir, paste0(key, "_train.csv")))
    write_csv(testing, file.path(output_dir, paste0(key, "_test.csv")))
    write.table(X, file.path(output_dir, paste0(key, "_Xtrain.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write.table(predict(fit, testing, type = "lpmatrix"), file.path(output_dir, paste0(key, "_Xtest.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write.table(penalty, file.path(output_dir, paste0(key, "_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write.table(rate_covariance(fit, training), file.path(output_dir, paste0(key, "_V.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write_csv(tibble(beta = coef(fit)), file.path(output_dir, paste0(key, "_beta.csv")))
    saveRDS(fit, file.path(output_dir, paste0(key, "_independent.rds")))
    manifest[[length(manifest) + 1]] <- tibble(key = key, english_name = species, fold = fold, heldout_year = heldout_year, theta = fit$family$getTheta(TRUE), coefficients = ncol(X))
  }
}
write_csv(bind_rows(manifest), file.path(output_dir, "manifest.csv"))
