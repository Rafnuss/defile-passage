# Load packages -------------------------------------------------------------
library(mgcv)
library(readr)
library(dplyr)
library(cli)

# Rebuild the frozen specification from retained inputs -------------------
args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args)) args[1] else 'logs/historical-transfer/input'
output <- if (length(args)) args[2] else 'logs/historical-transfer/design'
dir.create(output, showWarnings = FALSE)
manifest <- read_csv(file.path(input, 'manifest.csv'), show_col_types = FALSE)
for (key in manifest$key) {
  rows <- read_csv(file.path(input, paste0(key, '_components.csv')), show_col_types = FALSE)
  train <- rows[!rows$hidden, ]
  season <- smoothCon(s(doy, k = 8, bs = 'tp'), train, absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
  weather <- cbind(pmax(log1p(rows$rain_mm) - log(2), 0), rows$wind_u_m_s, rows$wind_v_m_s)
  scale <- apply(weather[!rows$hidden, ], 2, sd)
  weather <- sweep(weather, 2, scale, '/')
  write_csv(tibble(term = c('rain_hinge', 'wind_u', 'wind_v'), scale = scale), file.path(output, paste0(key, '_weather_scale.csv')))
  saveRDS(season, file.path(output, paste0(key, '_season_basis.rds')))
  clock <- as.numeric(as.POSIXct(rows$slot_start, tz = 'UTC')) / 3600 + .5
  phase <- 2 * pi * (clock %% 24) / 24
  harmonics <- cbind(sin(phase), cos(phase), sin(2 * phase), cos(2 * phase), sin(3 * phase), cos(3 * phase))
  X <- cbind(1, log1p(rows$rain_mm), PredictMat(season, rows), harmonics, weather, as.numeric(rows$tau < 0 | rows$tau > 1), model.matrix(~ factor(year), rows)[, -1, drop = FALSE])
  P <- matrix(0, ncol(X), ncol(X))
  P[3:9, 3:9] <- Reduce(`+`, lapply(season$S, function(x) x / mean(diag(x))))
  P[10:15, 10:15] <- diag(rep((1:3)^4, each = 2))
  write.table(X, file.path(output, paste0(key, '_year_weather_X.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  write.table(P, file.path(output, paste0(key, '_year_weather_penalty.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  file.copy(file.path(input, paste0(key, c('_components.csv', '_observations.csv'))), output, overwrite = TRUE)
  terms <- c('intercept', 'log_rain', paste0('season_', 1:7), paste0(rep(c('sin', 'cos'), 3), rep(1:3, each = 2)), 'rain_hinge', 'wind_u', 'wind_v', 'night', colnames(model.matrix(~ factor(year), rows))[-1])
  write_csv(tibble(term = terms), file.path(output, paste0(key, '_year_weather_terms.csv')))
  cli_alert_success('Prepared {key}: {ncol(X)} coefficients')
}
write_csv(manifest, file.path(output, 'manifest.csv'))
