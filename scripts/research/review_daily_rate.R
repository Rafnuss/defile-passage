# Load matched hidden counts ------------------------------------------------
library(dplyr)
library(tidyr)
library(readr)
library(ggplot2)
library(here)
set.seed(20261010)
output_dir <- here("logs", "hourly-weather-v3")
previous_dir <- here("logs", "hourly-weather-v2")
new <- read_csv(file.path(output_dir, "held_out_days.csv"), show_col_types = FALSE)
previous <- read_csv(file.path(previous_dir, "held_out_days.csv"), show_col_types = FALSE) |> filter(model == "weather") |> mutate(model = "gaussian_day")
production <- read_csv(file.path(previous_dir, "production_held_out_days.csv"), show_col_types = FALSE)
days <- bind_rows(new, previous, production) |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry"), block = paste(year, floor((as.integer(format(date, "%j")) - 1) / 7), sep = "-"))
matching <- days |> group_by(english_name, date, fold, gap) |> summarise(models = n_distinct(model), truths = n_distinct(count), .groups = "drop")
stopifnot(all(matching$models == 5), all(matching$truths == 1))

# Compare errors, mean calibration and predictive coverage -------------------
scores <- days |> group_by(english_name, model, gap, weather_group) |>
  summarise(days = n(), mae = mean(abs(predicted - count)), cover80 = mean(count >= q10 & count <= q90), cover95 = mean(count >= q025 & count <= q975), counted = sum(count), predicted = sum(predicted), .groups = "drop") |>
  mutate(bias_fraction = predicted / counted - 1)
write_csv(scores, file.path(output_dir, "comparison.csv"))
hours <- read_csv(file.path(output_dir, "held_out_hours.csv"), show_col_types = FALSE)
hour_scores <- hours |> mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry")) |> group_by(english_name, model, gap, weather_group) |>
  summarise(hours = n(), mae = mean(abs(predicted - count)), log_score = mean(log_score), maximum_mean_mcse = max(mean_mcse), .groups = "drop")
write_csv(hour_scores, file.path(output_dir, "hour_scores.csv"))

# Resample weeks for paired model differences -------------------------------
paired <- days |> select(english_name, date, fold, gap, weather_group, block, count, model, predicted) |> pivot_wider(names_from = model, values_from = predicted)
differences <- list()
for (candidate in c("weather_independent", "gamma_day_poisson", "gamma_day_flocks")) {
  for (reference in c("gaussian_day", "production_episode")) {
    for (rows in group_split(paired |> group_by(english_name, gap, weather_group))) {
      difference <- abs(rows[[candidate]] - rows$count) - abs(rows[[reference]] - rows$count)
      blocks <- unique(rows$block)
      bootstrap <- replicate(1000, {
        selected <- sample(blocks, length(blocks), replace = TRUE)
        index <- unlist(lapply(selected, function(block) which(rows$block == block)))
        mean(difference[index])
      })
      differences[[length(differences) + 1]] <- tibble(english_name = rows$english_name[1], gap = rows$gap[1], weather_group = rows$weather_group[1], model = candidate, reference = reference, mae_difference = mean(difference), lo = quantile(bootstrap, 0.025), hi = quantile(bootstrap, 0.975))
    }
  }
}
write_csv(bind_rows(differences), file.path(output_dir, "paired_mae_differences.csv"))
plot <- ggplot(scores |> filter(gap == "days"), aes(weather_group, mae, colour = model)) + geom_point(position = position_dodge(width = 0.6), size = 2) + facet_wrap(vars(english_name), scales = "free_y") + labs(x = "Weather over hidden observed intervals", y = "Daily mean absolute error (birds)", colour = "Model", subtitle = "Same seven-day masks; shared Gamma day multiplier has population mean one") + theme_bw()
ggsave(file.path(output_dir, "daily_rate_comparison.png"), plot, width = 11, height = 7, dpi = 180)
print(scores |> filter(gap == "days"), n = Inf)

# Verify inference and output reconciliation --------------------------------
diagnostics <- read_csv(file.path(output_dir, "diagnostics.csv"), show_col_types = FALSE)
stopifnot(nrow(diagnostics) == 60, all(diagnostics$converged), max(diagnostics$quadrature_loglik_difference) < 0.01)
reconciled <- hours |> group_by(english_name, model, fold, date) |> summarise(count = sum(count), predicted = sum(predicted), .groups = "drop") |> inner_join(new, by = c("english_name", "model", "fold", "date"), suffix = c("_hour", "_day"))
stopifnot(all(reconciled$count_hour == reconciled$count_day), all(abs(reconciled$predicted_hour - reconciled$predicted_day) < 1e-6))
cat("Daily multiplier comparison and saved-output checks completed\n")
