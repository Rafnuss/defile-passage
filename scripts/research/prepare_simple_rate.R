# Load packages -------------------------------------------------------------
library(mgcv)
library(readr)
library(dplyr)
library(cli)

# Build small training-only bases -------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
input_dir <- args[1]
output_dir <- args[2]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
manifest <- read_csv(file.path(input_dir, "manifest.csv"), show_col_types = FALSE)
if (!"--all" %in% args) manifest <- manifest |> filter(key %in% args[-c(1, 2)])
for (i in seq_len(nrow(manifest))) {
  key <- manifest$key[i]
  rows <- read_csv(file.path(input_dir, paste0(key, "_components.csv")), show_col_types = FALSE)
  training_rows <- if ("hidden" %in% names(rows)) !rows$hidden else rows$year != manifest$heldout_year[i]
  training <- rows[training_rows, ]
  basis <- list(
    smoothCon(s(doy, k = 8, bs = "tp"), training, absorb.cons = TRUE, null.space.penalty = TRUE)[[1]],
    smoothCon(s(tau, k = 8, bs = "cr"), training, knots = list(tau = c(-1, -.2, 0, .25, .5, .75, 1, 2)), absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
  )
  X <- cbind(1, log1p(rows$rain_mm), do.call(cbind, lapply(basis, PredictMat, data = rows)))
  penalty <- matrix(0, ncol(X), ncol(X))
  offset <- 2L
  for (smooth in basis) {
    indices <- offset + seq_len(ncol(smooth$X))
    S <- Reduce(`+`, lapply(smooth$S, function(x) x / mean(diag(x))))
    penalty[indices, indices] <- S
    offset <- offset + length(indices)
  }
  write.table(X, file.path(output_dir, paste0(key, "_X.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  write.table(penalty, file.path(output_dir, paste0(key, "_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  file.copy(file.path(input_dir, paste0(key, c("_components.csv", "_observations.csv"))), output_dir, overwrite = TRUE)
  saveRDS(basis, file.path(output_dir, paste0(key, "_basis.rds")))
  # Compare bounded-size alternatives, using training-only weather scaling.
  weather <- cbind(pmax(log1p(rows$rain_mm) - log(2), 0), rows$wind_u_m_s, rows$wind_v_m_s, log1p(rows$rain_previous_24h_mm))
  weather_training <- training_rows
  scale <- apply(weather[weather_training, ], 2, sd)
  weather <- sweep(weather, 2, scale, "/")
  clock <- as.numeric(as.POSIXct(rows$slot_start, tz = "UTC", format = "%Y-%m-%dT%H:%M:%SZ")) / 3600 + .5
  phase <- 2 * pi * (clock %% 24) / 24
  harmonics <- cbind(sin(phase), cos(phase), sin(2 * phase), cos(2 * phase), sin(3 * phase), cos(3 * phase))
  for (variant in c("rain_weather", "rain_daylight", "cyclic_clock")) {
    design <- switch(variant, rain_weather = cbind(X, weather), rain_daylight = cbind(X, weather[, 1:3], as.numeric(rows$tau < 0 | rows$tau > 1)), cyclic_clock = cbind(X[, 1:9], harmonics, weather[, 1:3], as.numeric(rows$tau < 0 | rows$tau > 1)))
    P <- matrix(0, ncol(design), ncol(design))
    if (variant == "cyclic_clock") {
      P[1:9, 1:9] <- penalty[1:9, 1:9]
      P[10:15, 10:15] <- diag(rep((1:3)^4, each = 2))
    } else P[seq_len(ncol(X)), seq_len(ncol(X))] <- penalty
    write.table(design, file.path(output_dir, paste0(key, "_", variant, "_X.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
    write.table(P, file.path(output_dir, paste0(key, "_", variant, "_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  }
  if ("hidden" %in% names(rows)) {
    annual <- model.matrix(~ factor(year), rows)[, -1, drop = FALSE]
    clock_design <- cbind(X[, 1:9], harmonics, weather[, 1:3], as.numeric(rows$tau < 0 | rows$tau > 1))
    seasonal_coordinate <- (rows$doy - mean(training$doy)) / sd(training$doy)
    write_csv(tibble(center = mean(training$doy), scale = sd(training$doy)), file.path(output_dir, paste0(key, "_season_scale.csv")))
    for (variant in c("year_weather", "year_clear", "year_season_weather", "year_episode_weather")) {
      keep <- if (variant != "year_clear") seq_len(19) else c(1, 3:15, 19)
      design <- cbind(clock_design[, keep], annual)
      if (variant == "year_season_weather") design <- cbind(design, annual * seasonal_coordinate, annual * seasonal_coordinate^2)
      terms <- c("intercept", "log_rain", paste0("season_", 1:7), paste0(rep(c("sin", "cos"), 3), rep(1:3, each = 2)), "rain_hinge", "wind_u", "wind_v", "night")[keep]
      terms <- c(terms, colnames(annual))
      if (variant == "year_season_weather") terms <- c(terms, paste0(colnames(annual), "_season_linear"), paste0(colnames(annual), "_season_quadratic"))
      if (variant == "year_episode_weather") {
        episode <- smoothCon(s(doy, k = 8, bs = "cr"), training, absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
        episode_design <- PredictMat(episode, data = rows)
        episode_center <- colMeans(PredictMat(episode, data = data.frame(doy = seq(min(training$doy), max(training$doy)))))
        episode_design <- sweep(episode_design, 2, episode_center, "-")
        years <- sort(unique(rows$year))
        design <- cbind(design, do.call(cbind, lapply(years, function(year) episode_design * (rows$year == year))))
        terms <- c(terms, unlist(lapply(years, function(year) paste0("episode_", year, "_", 1:7))))
        saveRDS(list(basis = episode, center = episode_center, years = years), file.path(output_dir, paste0(key, "_episode_basis.rds")))
      }
      P <- matrix(0, ncol(design), ncol(design))
      clock_penalty <- matrix(0, 19, 19)
      clock_penalty[1:9, 1:9] <- penalty[1:9, 1:9]
      clock_penalty[10:15, 10:15] <- diag(rep((1:3)^4, each = 2))
      P[seq_along(keep), seq_along(keep)] <- clock_penalty[keep, keep]
      if (variant == "year_episode_weather") {
        episode_penalty <- matrix(0, ncol(design), ncol(design))
        S <- Reduce(`+`, lapply(episode$S, function(x) x / mean(diag(x)))) + diag(7)
        for (j in seq_along(years)) {
          indices <- 22 + (j - 1) * 7 + seq_len(7)
          episode_penalty[indices, indices] <- S
        }
        write.table(episode_penalty, file.path(output_dir, paste0(key, "_", variant, "_episode_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
      }
      write.table(design, file.path(output_dir, paste0(key, "_", variant, "_X.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
      write.table(P, file.path(output_dir, paste0(key, "_", variant, "_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
      write_csv(tibble(term = terms), file.path(output_dir, paste0(key, "_", variant, "_terms.csv")))
    }
  }
  write_csv(tibble(term = c("rain_hinge", "wind_u", "wind_v", "previous_rain"), scale = scale), file.path(output_dir, paste0(key, "_weather_scale.csv")))
  cli_alert_success("Prepared {key}: {ncol(X)} rate coefficients")
}
write_csv(manifest, file.path(output_dir, "manifest.csv"))
