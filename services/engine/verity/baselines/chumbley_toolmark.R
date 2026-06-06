#!/usr/bin/env Rscript
# Baseline COMPETITOR for the Phase-4 toolmark head-to-head: the Chumbley
# non-random U-statistic (toolmaRk::chumbley_non_random, the specialist toolmark
# algorithm) scored on every pair of the GPL ameslab screwdriver profiles.
# Mirrors bulletxtrctr_score.R — R + a GPL dataset/algorithm, isolated from
# Verity's runtime, used only to compare against. Writes (i, j, U, p_value, ids).
#
# Usage:  Rscript chumbley_toolmark.R <out.csv>

suppressMessages(library(toolmaRk))
data(ameslab, package = "toolmaRk")

args <- commandArgs(trailingOnly = TRUE)
out <- args[1]
n <- nrow(ameslab)
total <- n * (n - 1) / 2

rows <- vector("list", total)
k <- 0
for (i in 1:(n - 1)) {
  for (j in (i + 1):n) {
    d1 <- matrix(ameslab$profile[[i]][[1]], ncol = 1)
    d2 <- matrix(ameslab$profile[[j]][[1]], ncol = 1)
    res <- tryCatch(chumbley_non_random(d1, d2),
                    error = function(e) list(U = NA, p_value = NA))
    k <- k + 1
    rows[[k]] <- data.frame(
      i = i - 1L, j = j - 1L,                       # 0-indexed to match Python
      U = ifelse(is.null(res$U), NA, res$U),
      p_value = ifelse(is.null(res$p_value), NA, res$p_value),
      id_i = as.character(ameslab$ID[i]),
      id_j = as.character(ameslab$ID[j]),
      stringsAsFactors = FALSE
    )
    cat(sprintf("pair %d/%d (%d,%d) U=%s\n", k, total, i, j,
                ifelse(is.na(rows[[k]]$U), "NA", sprintf("%.2f", rows[[k]]$U))))
  }
}
write.csv(do.call(rbind, rows), out, row.names = FALSE)
cat("wrote", out, "\n")
