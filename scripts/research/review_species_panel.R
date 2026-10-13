# Load only the priority-species comparison ---------------------------------
library(dplyr)
library(tidyr)
library(readr)
library(ggplot2)
library(here)
set.seed(20261010)
output_dir <- here("logs", "hourly-weather-panel-v4")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
input_dirs <- c(here("logs", "hourly-weather-priority"), here("logs", "hourly-weather-passerines"))
selection <- read_tsv(here("scripts", "research", "weather_species.tsv"), show_col_types = FALSE)
new <- bind_rows(lapply(input_dirs, function(path) read_csv(file.path(path, "held_out_days.csv"), show_col_types = FALSE)))
production <- bind_rows(lapply(input_dirs, function(path) read_csv(file.path(path, "production_held_out_days.csv"), show_col_types = FALSE)))
days <- bind_rows(new, production) |> left_join(selection, by = "english_name") |>
  mutate(weather_group = ifelse(rain_mm >= 0.1, "wet", "dry"), block = paste(year, floor((as.integer(format(date, "%j")) - 1) / 7), sep = "-"))
matching <- days |> group_by(english_name, date, fold, gap) |> summarise(models = n_distinct(model), truths = n_distinct(count), .groups = "drop")
stopifnot(n_distinct(days$english_name) == nrow(selection), all(days$recording_scope != "unverified"), all(matching$models == 4), all(matching$truths == 1))

# Report each species, with equal-species summaries kept separate ------------
scores <- days |> group_by(english_name, model, gap, weather_group) |>
  summarise(days = n(), mae = mean(abs(predicted - count)), cover80 = mean(count >= q10 & count <= q90), cover95 = mean(count >= q025 & count <= q975), counted = sum(count), predicted = sum(predicted), .groups = "drop") |> mutate(bias_fraction = predicted / counted - 1)
write_csv(scores, file.path(output_dir, "comparison.csv"))
relative <- scores |> select(english_name, model, gap, weather_group, mae, bias_fraction, cover95) |>
  left_join(scores |> filter(model == "production_episode") |> select(english_name, gap, weather_group, production_mae = mae), by = c("english_name", "gap", "weather_group")) |> mutate(mae_ratio = mae / production_mae)
macro <- relative |> group_by(model, gap, weather_group) |>
  summarise(species = n(), mean_mae_ratio = mean(mae_ratio), median_mae_ratio = median(mae_ratio), species_better_than_production = sum(mae_ratio < 1), mean_absolute_bias = mean(abs(bias_fraction)), mean_cover95 = mean(cover95), .groups = "drop")
write_csv(macro, file.path(output_dir, "species_balanced_scores.csv"))

# Compare paired errors with calendar-week resampling -----------------------
paired <- days |> select(english_name, date, fold, gap, weather_group, block, count, model, predicted) |> pivot_wider(names_from = model, values_from = predicted)
differences <- list()
for (reference in c("gamma_day_flocks", "production_episode")) {
  for (rows in group_split(paired |> group_by(english_name, gap, weather_group))) {
    difference <- abs(rows$gamma_day_smoothing - rows$count) - abs(rows[[reference]] - rows$count)
    blocks <- unique(rows$block)
    bootstrap <- replicate(1000, {
      selected <- sample(blocks, length(blocks), replace = TRUE)
      index <- unlist(lapply(selected, function(block) which(rows$block == block)))
      mean(difference[index])
    })
    differences[[length(differences) + 1]] <- tibble(english_name = rows$english_name[1], gap = rows$gap[1], weather_group = rows$weather_group[1], reference = reference, mae_difference = mean(difference), lo = quantile(bootstrap, 0.025), hi = quantile(bootstrap, 0.975))
  }
}
write_csv(bind_rows(differences), file.path(output_dir, "paired_mae_differences.csv"))

# Retain smoothing termination and numerical accuracy -----------------------
manifest <- bind_rows(lapply(input_dirs, function(path) read_csv(file.path(path, "manifest.csv"), show_col_types = FALSE) |> mutate(input_dir = path)))
traces <- list()
for (i in seq_len(nrow(manifest))) {
  trace <- read_csv(file.path(manifest$input_dir[i], paste0(manifest$key[i], "_smoothing_trace.csv")), show_col_types = FALSE)
  stopifnot(all(diff(trace$evidence) <= 1e-8))
  traces[[i]] <- tibble(english_name = manifest$english_name[i], fold = manifest$fold[i], steps = max(trace$step), status = last(trace$status), evidence_improvement = first(trace$evidence) - last(trace$evidence), final_inner_gradient = last(trace$inner_gradient))
}
write_csv(bind_rows(traces), file.path(output_dir, "smoothing_status.csv"))
diagnostics <- bind_rows(lapply(input_dirs, function(path) read_csv(file.path(path, "diagnostics.csv"), show_col_types = FALSE)))
stopifnot(nrow(diagnostics) == 3 * nrow(manifest), all(diagnostics$converged), max(diagnostics$quadrature_loglik_difference) < 0.01)
hours <- bind_rows(lapply(input_dirs, function(path) read_csv(file.path(path, "held_out_hours.csv"), show_col_types = FALSE)))
write_csv(days, file.path(output_dir, "held_out_days.csv"))
write_csv(hours, file.path(output_dir, "held_out_hours.csv"))
write_csv(diagnostics, file.path(output_dir, "diagnostics.csv"))
reconciled <- hours |> group_by(english_name, model, fold, date) |> summarise(count = sum(count), predicted = sum(predicted), .groups = "drop") |> inner_join(new, by = c("english_name", "model", "fold", "date"), suffix = c("_hour", "_day"))
stopifnot(all(reconciled$count_hour == reconciled$count_day), all(abs(reconciled$predicted_hour - reconciled$predicted_day) < 1e-6))

# Show variation across the deliberately varied panel -----------------------
plot <- ggplot(scores |> filter(gap == "days"), aes(weather_group, mae, colour = model)) + geom_point(position = position_dodge(width = 0.6), size = 2) + facet_wrap(vars(english_name), scales = "free_y", ncol = 3) + labs(x = "Weather over hidden observed intervals", y = "Daily mean absolute error (birds)", colour = "Model", subtitle = "Sixteen species; recent passerine recording scope confirmed by the user") + theme_bw()
ggsave(file.path(output_dir, "species_panel_comparison.png"), plot, width = 13, height = 10, dpi = 180)
print(macro, n = Inf)
print(bind_rows(traces) |> count(status), n = Inf)
cat("Species-panel comparison, scope and saved-output checks completed\n")
