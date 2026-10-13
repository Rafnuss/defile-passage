# Approximate information in nearly empty seasonal tails --------------------
# Same convention as trend.MIN_RATE: this changes covariance, not fitted means or counts.
MIN_DAILY_RATE <- 0.1
RATE_FLOORS <- c(0.01, MIN_DAILY_RATE, 1)
N_DRAWS <- 500

rate_covariance <- function(fit, training, min_daily_rate = MIN_DAILY_RATE) {
  X <- predict(fit, newdata = training, type = "lpmatrix")
  mu <- as.numeric(predict(fit, newdata = training, type = "response"))
  daylight_hours <- as.numeric(difftime(training$dusk, training$dawn, units = "hours"))
  minimum <- min_daily_rate * training$exposure_hours / daylight_hours
  theta <- fit$family$getTheta(TRUE)
  added_information <- (pmax(mu, minimum) - mu) * theta / (theta + mu)
  precision <- chol2inv(chol(fit$Vp)) + crossprod(X * sqrt(added_information))
  chol2inv(chol(precision))
}
