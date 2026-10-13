# Load packages -----------------------------------------------------------
library(mgcv)
library(readr)
library(cli)

# Add a small centered within-year smooth to the frozen weather design ----
args <- commandArgs(trailingOnly = TRUE)
output <- args[1]
manifest <- read_csv(file.path(output, 'manifest.csv'), show_col_types = FALSE)
for (key in manifest$key) {
  rows <- read_csv(file.path(output, paste0(key, '_components.csv')), show_col_types = FALSE)
  train <- rows[!rows$hidden, ]
  episode <- smoothCon(s(doy, k = 5, bs = 'cr'), train, absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
  center <- colMeans(PredictMat(episode, data.frame(doy = seq(min(train$doy), max(train$doy)))))
  basis <- sweep(PredictMat(episode, rows), 2, center, '-')
  years <- sort(unique(rows$year))
  X <- do.call(cbind, lapply(years, function(year) basis * (rows$year == year)))
  S <- Reduce(`+`, lapply(episode$S, function(x) x / mean(diag(x)))) + diag(4)
  P <- kronecker(diag(length(years)), S)
  write.table(X, file.path(output, paste0(key, '_episode_X.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  write.table(P, file.path(output, paste0(key, '_episode_penalty.csv')), sep = ',', row.names = FALSE, col.names = FALSE)
  write_csv(data.frame(term = unlist(lapply(years, function(year) paste0('episode_', year, '_', 1:4)))), file.path(output, paste0(key, '_episode_terms.csv')))
  saveRDS(list(basis = episode, center = center, years = years), file.path(output, paste0(key, '_episode_basis.rds')))
  cli_alert_success('Prepared {key}: {ncol(X)} episode coefficients')
}
