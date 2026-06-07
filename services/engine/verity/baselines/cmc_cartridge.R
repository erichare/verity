#!/usr/bin/env Rscript
# Baseline COMPETITOR for the cartridge-case head-to-head: the Congruent Matching
# Cells (CMC) count -- cmcR, the specialist breech-face method -- on every pair of
# the Fadul masked scans. Mirrors bulletxtrctr_score.R / chumbley_toolmark.R: R + a
# CSAFE/GPL method, isolated from Verity's runtime, used only to compare against.
#
# RESUMABLE: appends one row per pair to <out.csv> and skips pairs already present,
# so a killed run can be re-launched and continues (the CMC pipeline is slow:
# per-pair cell registration over a rotation grid).
#
# cmcR is CRAN-archived; install with
#   remotes::install_github("CSAFE-ISU/cmcR")
# Usage:  Rscript cmc_cartridge.R <fadulMasked_dir> <out.csv> [theta_by=6]

suppressMessages({
  library(cmcR)
  library(x3ptools)
  library(dplyr)
  library(purrr)
})

args <- commandArgs(trailingOnly = TRUE)
masked_dir <- args[1]
out <- args[2]
theta_by <- if (length(args) >= 3) as.numeric(args[3]) else 6

files <- sort(list.files(masked_dir, pattern = "^Fadul [0-9]+-[0-9]+\\.x3p$", full.names = TRUE))
slide <- as.integer(sub("^Fadul ([0-9]+)-.*$", "\\1", basename(files)))

# cmcR 0.1.11 preprocessing (its own exterior/interior crop handles the masked scans).
preprocess <- function(path) {
  read_x3p(path) %>%
    preProcess_crop(region = "exterior", offset = -30) %>%
    preProcess_crop(region = "interior", offset = 200) %>%
    preProcess_removeTrend(statistic = "quantile", tau = .5, method = "fn") %>%
    preProcess_gaussFilter() %>%
    x3p_sample()
}

cmc_count <- function(ref, tgt) {
  feats <- purrr::map_dfr(seq(-30, 30, by = theta_by),
                          ~ comparison_allTogether(reference = ref, target = tgt, theta = .))
  classif <- feats %>%
    dplyr::mutate(cmc = decision_CMC(cellIndex = cellIndex, x = x, y = y, theta = theta,
                                     corr = pairwiseCompCor,
                                     xThresh = 20, thetaThresh = 6, corrThresh = .5))
  sum(classif$cmc == "CMC", na.rm = TRUE)
}

done <- if (file.exists(out)) {
  d <- utils::read.csv(out, stringsAsFactors = FALSE)
  paste(d$i, d$j)
} else {
  cat("i,j,cmc,slide_i,slide_j\n", file = out)
  character(0)
}

n <- length(files)
pre <- vector("list", n)  # processed-surface cache (each scan preprocessed once)
for (i in 1:(n - 1)) {
  for (j in (i + 1):n) {
    if (paste(i - 1, j - 1) %in% done) next
    if (is.null(pre[[i]])) pre[[i]] <- preprocess(files[i])
    if (is.null(pre[[j]])) pre[[j]] <- preprocess(files[j])
    cmc <- tryCatch(cmc_count(pre[[i]], pre[[j]]), error = function(e) NA)
    cat(sprintf("%d,%d,%s,%d,%d\n", i - 1, j - 1, ifelse(is.na(cmc), "NA", cmc), slide[i], slide[j]),
        file = out, append = TRUE)
    cat(sprintf("(%d,%d) slides %d/%d CMC=%s\n", i, j, slide[i], slide[j],
                ifelse(is.na(cmc), "NA", cmc)))
  }
}
cat("done ->", out, "\n")
