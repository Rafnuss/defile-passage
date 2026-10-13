# Load packages -------------------------------------------------------------
library(mgcv)
library(dplyr)
library(readr)
library(cli)

# Prepare a simpler positive-count component using training observations -----
args <- commandArgs(trailingOnly = TRUE)
input_dir <- args[1]
manifest <- read_csv(file.path(input_dir, "manifest.csv"), show_col_types = FALSE) |> filter(fold != 4)
for (record in seq_len(nrow(manifest))) {
  key <- manifest$key[record]
  training <- read_csv(file.path(input_dir, paste0(key, "_train.csv")), show_col_types = FALSE) |> mutate(year_factor = factor(year))
  testing <- read_csv(file.path(input_dir, paste0(key, "_test.csv")), show_col_types = FALSE) |> mutate(year_factor = factor(year, levels = levels(training$year_factor)))
  formula <- count ~ year_factor + s(doy, k = 12) + s(tau, k = 6) + log_rain + log_previous_rain + wind_u_m_s + wind_v_m_s + radiation_100 + low_cloud_fraction + offset(log(exposure_hours))
  if (manifest$fold[record] >= 5) formula <- update(formula, . ~ . - year_factor)
  cli_alert_info("Preparing positive counts: {key}")
  fit <- bam(formula, data = training |> filter(count > 0), family = nb(), method = "fREML", discrete = TRUE, select = TRUE, nthreads = 1)
  Z <- predict(fit, training, type = "lpmatrix")
  penalty <- matrix(0, ncol(Z), ncol(Z))
  for (smooth in fit$smooth) {
    index <- smooth$first.para:smooth$last.para
    for (j in seq_along(smooth$S)) penalty[index, index] <- penalty[index, index] + fit$sp[smooth$first.sp + j - 1] * smooth$S[[j]]
  }
  write.table(Z, file.path(input_dir, paste0(key, "_Ztrain.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  write.table(predict(fit, testing, type = "lpmatrix"), file.path(input_dir, paste0(key, "_Ztest.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  write.table(penalty, file.path(input_dir, paste0(key, "_positive_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  write_csv(tibble(beta = coef(fit), term = names(coef(fit))), file.path(input_dir, paste0(key, "_positive_beta.csv")))
  saveRDS(fit, file.path(input_dir, paste0(key, "_positive_anchor.rds")))
}
