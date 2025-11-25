# ============================================
#  Aagos – Environmental Change Figures
#  (Prof logic, local D:/Aagos_2025)
# ============================================

library(tidyverse)
library(cowplot)
library(hexbin)

# ---------- 0. Paths + theme ----------
theme_set(theme_cowplot())

# Base folder on local drive D:
base_dir <- "D:/Aagos_2025"

# summary.csv yahan hona chahiye:
summary_data_path <- file.path(base_dir, "summary.csv")

# Figures isi folder main save honge:
plot_dir <- base_dir
dir.create(plot_dir, showWarnings = FALSE)

sig_thresh <- 0.5

# ---------- 1. Load + preprocess summary.csv ----------
summary_data <- read_csv(summary_data_path, show_col_types = FALSE) %>%
  mutate(
    BIT_FLIP_PROB = as.factor(BIT_FLIP_PROB),
    DRIFT = TOURNAMENT_SIZE == 1
  ) %>%
  mutate(
    chg_rate_label = case_when(
      DRIFT ~ "drift",
      CHANGE_MAGNITUDE == "0" ~ "static",
      CHANGE_FREQUENCY == "0" ~ "static",
      .default = paste(CHANGE_MAGNITUDE, CHANGE_FREQUENCY, sep = "/")
    )
  ) %>%
  mutate(
    chg_rate_label = factor(
      chg_rate_label,
      levels = c(
        "drift",
        "static",
        "1/256","1/128","1/64","1/32","1/16","1/8",
        "1/4","1/2","1/1",
        "2/1","4/1","8/1","16/1","32/1","64/1",
        "128/1","256/1","512/1",
        "1024/1","2048/1","4096/1"
      )
    )
  )

# Phase 0 + gradient only
phase0_grad <- summary_data %>%
  filter(
    evo_phase == 0,
    update == 50000,
    GRADIENT_MODEL == 1
  )

# Phase 1 + gradient only
phase1_grad <- summary_data %>%
  filter(
    evo_phase == 1,
    update == 60000,
    GRADIENT_MODEL == 1
  )

# ============================================
#  Figure 2 — Coding Sites vs Environmental Change (Phase 0)
# ============================================

fig2 <- ggplot(phase0_grad,
               aes(x = chg_rate_label, y = coding_sites)) +
  geom_boxplot(
    color = "black",
    fill  = "white",
    outlier.shape = 16,
    outlier.size  = 0.8
  ) +
  scale_y_continuous(
    limits = c(0, 130),
    breaks = seq(0, 130, 20)
  ) +
  labs(
    x = "Environmental Change",
    y = "Coding Sites (best genotype)"
  ) +
  theme(legend.position = "none")

ggsave(
  file = file.path(plot_dir, "Figure2_CodingSites_vs_EnvChange_PAPER.png"),
  plot = fig2,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

# ============================================
#  Figure 3a — Fitness vs Environmental Change (Phase 1)
# ============================================

fig3a <- ggplot(phase1_grad,
                aes(x = chg_rate_label, y = fitness)) +
  geom_boxplot(
    color = "black",
    fill  = "white",
    outlier.shape = 16,
    outlier.size  = 0.8
  ) +
  scale_y_continuous(
    limits = c(10, 16),
    breaks = seq(10, 16, 1)
  ) +
  labs(
    x = "Environmental Change",
    y = "Fitness"
  ) +
  theme(legend.position = "none")

ggsave(
  file = file.path(plot_dir, "Figure3a_Fitness_vs_EnvChange_PAPER.png"),
  plot = fig3a,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

# ============================================
#  Figure 3b — Fitness vs Coding Sites (Phase 1)
# ============================================

fig3b <- ggplot(phase1_grad,
                aes(x = coding_sites, y = fitness)) +
  geom_hex(alpha = 0.95) +
  scale_x_continuous(
    name   = "Coding Sites",
    limits = c(0, 130),
    breaks = seq(0, 130, 20)
  ) +
  scale_fill_continuous(
    type = "viridis",
    trans = "log",
    name = "Count",
    breaks = c(1, 10, 100)
  ) +
  labs(
    x = "Coding Sites",
    y = "Fitness"
  ) +
  theme(legend.position = "none")

ggsave(
  file = file.path(plot_dir, "Figure3b_Fitness_vs_CodingSites_PAPER.png"),
  plot = fig3b,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)
