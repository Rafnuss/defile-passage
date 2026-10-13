# Load packages -----------------------------------------------------------
library(mgcv)
library(readr)
library(cli)

# Change only the common seasonal basis on the existing paired inputs -----
input <- 'logs/history-episode/design'
output <- 'logs/history-season/design'
dir.create(output, recursive = TRUE, showWarnings = FALSE)
manifest <- read_csv(file.path(input, 'manifest.csv'), show_col_types = FALSE)
for (key in manifest$key) {
  rows <- read_csv(file.path(input, paste0(key, '_components.csv')), show_col_types = FALSE)
  season <- smoothCon(s(doy, k = 20, bs = 'tp'), rows[!rows$hidden, ], absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
  X <- as.matrix(read_csv(file.path(input, paste0(key, '_year_weather_X.csv')), col_names = FALSE, show_col_types = FALSE))
  P <- as.matrix(read_csv(file.path(input, paste0(key, '_year_weather_penalty.csv')), col_names = FALSE, show_col_types = FALSE))
  keep <- c(1:2, 10:ncol(X))
  design <- cbind(X[, 1:2], PredictMat(season, rows), X[, 10:ncol(X)])
  penalty <- matrix(0, ncol(design), ncol(design))
  other <- c(1:2, 22:ncol(design))
  penalty[other, other] <- P[keep, keep]
  penalty[3:21, 3:21] <- Reduce(`+`, lapply(season$S, function(x) x / mean(diag(x))))
  stopifnot(identical(design[, other], X[, keep]))
  write.table(design, file.path(output, paste0(key, '_X.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  write.table(penalty, file.path(output, paste0(key, '_penalty.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  terms <- read_csv(file.path(input, paste0(key, '_year_weather_terms.csv')), show_col_types = FALSE)$term
  write_csv(data.frame(term = c(terms[1:2], paste0('season_', 1:19), terms[10:length(terms)])), file.path(output, paste0(key, '_terms.csv')))
  saveRDS(season, file.path(output, paste0(key, '_season_basis.rds')))
  cli_alert_success('Prepared {key}: {ncol(design)} coefficients')
}
write_csv(manifest, file.path(output, 'manifest.csv'))
