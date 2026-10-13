# Load packages -------------------------------------------------------------
library(mgcv)
library(readr)
library(dplyr)
library(cli)

# Build time bases over a complete civil-daylight coordinate range ----------
args <- commandArgs(trailingOnly = TRUE)
input_dir <- args[1]
original_dir <- args[2]
manifest <- read_csv(file.path(input_dir, "manifest.csv"), show_col_types = FALSE)
for (i in seq_len(nrow(manifest))) {
  key <- manifest$key[i]
  rows <- read_csv(file.path(input_dir, paste0(key, "_components.csv")), show_col_types = FALSE)
  training <- if (manifest$fold[i] >= 5) rows |> filter(year != manifest$heldout_year[i]) else rows
  fit <- readRDS(file.path(original_dir, paste0(key, "_independent.rds")))
  original_time <- fit$smooth[vapply(fit$smooth, function(x) x$label %in% c("s(tau)", "ti(tau,doy)"), logical(1))]
  time <- list(
    smoothCon(s(tau, k = 15, bs = "cr"), training, knots = list(tau = c(-1, -.5, -.2, seq(0, 1, length.out = 9), 1.25, 1.5, 2)), absorb.cons = TRUE, null.space.penalty = TRUE)[[1]],
    smoothCon(ti(tau, doy, k = c(8, 8), bs = c("cr", "tp")), training, knots = list(tau = c(-1, -.3, 0, .25, .5, .75, 1, 2)), absorb.cons = TRUE, null.space.penalty = TRUE)[[1]]
  )
  X <- do.call(cbind, lapply(time, PredictMat, data = rows))
  penalty <- matrix(0, ncol(X), ncol(X))
  offset <- 0L
  for (j in seq_along(time)) {
    indices <- offset + seq_len(ncol(time[[j]]$X))
    for (k in seq_along(time[[j]]$S)) penalty[indices, indices] <- penalty[indices, indices] + fit$sp[original_time[[j]]$first.sp + k - 1] * time[[j]]$S[[k]]
    offset <- offset + length(indices)
  }
  cli_alert_info("Preparing full-clock time basis: {key}")
  write.table(X, file.path(input_dir, paste0(key, "_time_X.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  write.table(penalty, file.path(input_dir, paste0(key, "_time_penalty.csv")), sep = ",", row.names = FALSE, col.names = FALSE)
  saveRDS(time, file.path(input_dir, paste0(key, "_time_basis.rds")))
}
