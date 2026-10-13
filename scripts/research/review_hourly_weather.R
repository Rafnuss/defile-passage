# Load completed validation and support diagnostics -------------------------
library(dplyr)
library(tidyr)
library(readr)
library(ggplot2)
library(here)
set.seed(20261010)
args <- commandArgs(trailingOnly = TRUE)
output_dir <- if (length(args)) args[1] else here("logs", "hourly-weather-v2")
hourly <- read_csv(file.path(output_dir, "held_out_days.csv"), show_col_types = FALSE)
production <- read_csv(file.path(output_dir, "production_held_out_days.csv"), show_col_types = FALSE)
days <- bind_rows(hourly, production) |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry"), block = paste(year, floor((as.integer(format(date, "%j")) - 1) / 7), sep = "-"))
matching <- days |>
  group_by(english_name, date, fold, gap) |>
  summarise(models = n_distinct(model), truths = n_distinct(count), .groups = "drop")
stopifnot(all(matching$models == n_distinct(days$model)), all(matching$truths == 1))

# Compare every architecture on identical hidden counts ----------------------
scores <- days |>
  group_by(english_name, model, gap, weather_group) |>
  summarise(days = n(), mae = mean(abs(predicted - count)), cover80 = mean(count >= q10 & count <= q90), cover95 = mean(count >= q025 & count <= q975), counted = sum(count), predicted = sum(predicted), .groups = "drop") |>
  mutate(bias_fraction = predicted / counted - 1)
write_csv(scores, file.path(output_dir, "production_comparison.csv"))
paired <- days |>
  select(english_name, date, fold, gap, weather_group, block, count, model, predicted) |>
  pivot_wider(names_from = model, values_from = predicted)
differences <- list()
for (candidate in setdiff(unique(days$model), "production_episode")) {
  for (rows in group_split(paired |> group_by(english_name, gap, weather_group))) {
    difference <- abs(rows[[candidate]] - rows$count) - abs(rows$production_episode - rows$count)
    blocks <- unique(rows$block)
    # Resample calendar-week clusters, keeping neighbouring days together.
    bootstrap <- replicate(1000, {
      selected <- sample(blocks, length(blocks), replace = TRUE)
      index <- unlist(lapply(selected, function(block) which(rows$block == block)))
      mean(difference[index])
    })
    differences[[length(differences) + 1]] <- tibble(english_name = rows$english_name[1], gap = rows$gap[1], weather_group = rows$weather_group[1], model = candidate, mae_difference = mean(difference), lo = quantile(bootstrap, 0.025), hi = quantile(bootstrap, 0.975))
  }
}
write_csv(bind_rows(differences), file.path(output_dir, "paired_mae_differences.csv"))

# Inspect changes in time flexibility and correlated weather predictors ------
basis <- read_csv(file.path(output_dir, "basis_checks.csv"), show_col_types = FALSE)
concurvity <- read_csv(file.path(output_dir, "concurvity.csv"), show_col_types = FALSE)
write_csv(basis |> filter(term %in% c("s(doy)", "s(tau)", "ti(tau,doy)")), file.path(output_dir, "time_basis_review.csv"))
write_csv(concurvity |> filter(term %in% c("s(log_rain)", "s(log_previous_rain)", "s(wind_u_m_s)", "s(wind_v_m_s)", "s(radiation_100)", "s(low_cloud_fraction)")), file.path(output_dir, "weather_concurvity_review.csv"))
comparison_plot <- ggplot(scores |> filter(gap == "days"), aes(weather_group, mae, colour = model)) +
  geom_point(position = position_dodge(width = 0.6), size = 2) + facet_wrap(vars(english_name), scales = "free_y") +
  labs(x = "Weather over the hidden observed intervals", y = "Mean absolute error of hidden daily counts (birds)", colour = "Model", subtitle = "Identical seven-day masks; production profile and all model parameters refitted within folds") + theme_bw()
ggsave(file.path(output_dir, "production_comparison.png"), comparison_plot, width = 11, height = 7, dpi = 180)
print(scores |> filter(gap == "days"), n = Inf)
cat("Matched production comparison and diagnostic review saved\n")
