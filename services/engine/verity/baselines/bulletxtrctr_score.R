#!/usr/bin/env Rscript
# bulletxtrctr land-to-land matchscore baseline — a COMPETITOR in Verity's
# validation harness only (never in Verity's runtime path).
#
# Reads a manifest CSV (file, barrel, bullet, land) of x3p lands named by their
# content hash, runs the standard bulletxtrctr pipeline to a per-land signature
# (cached by content hash as RDS), scores every land pair with the bundled
# random forest (rtrees), and aggregates to a bullet-to-bullet score = the best
# mean diagonal over cyclic land rotations (the same aggregation Verity's CCF
# uses, so the two systems differ only in the land score).
#
# Usage: Rscript bulletxtrctr_score.R <manifest.csv> <land_x3p_dir> <sig_cache_dir> <out.csv>

suppressMessages({
  library(bulletxtrctr)
  library(x3ptools)
  library(randomForest)
})

args <- commandArgs(trailingOnly = TRUE)
manifest_path <- args[[1]]
x3p_dir <- args[[2]]
cache_dir <- args[[3]]
out_path <- args[[4]]
dir.create(cache_dir, showWarnings = FALSE, recursive = TRUE)

manifest <- read.csv(manifest_path, stringsAsFactors = FALSE)

# --- per-land signature (cached by content-hash filename) ------------------- #
signature_for <- function(fname) {
  cache <- file.path(cache_dir, paste0(fname, ".rds"))
  if (file.exists(cache)) {
    return(readRDS(cache))
  }
  out <- tryCatch({
    x <- x3p_m_to_mum(read_x3p(file.path(x3p_dir, paste0(fname, ".x3p"))))
    # NBTRD bullet scans are stored with the long (travel) axis horizontal;
    # bulletxtrctr's crosscut pipeline expects it vertical. Rotating 90° lifts a
    # same-source land match from ~0.3 to ~0.95 (verified). Without it the RF
    # sees garbage and reports ~0.3 for everything.
    x <- rotate_x3p(x, angle = 90)
    cc <- x3p_crosscut_optimize(x)
    ccd <- x3p_crosscut(x, cc)
    gr <- cc_locate_grooves(ccd, method = "middle", adjust = 30, return_plot = FALSE)
    sig <- cc_get_signature(ccd, gr, span1 = 0.75, span2 = 0.03)
    list(sig = sig$sig, resolution = x$header.info$incrementY)
  }, error = function(e) list(sig = NA, resolution = NA))
  saveRDS(out, cache)
  out
}

cat("computing", nrow(manifest), "land signatures ...\n")
sigs <- lapply(manifest$file, signature_for)
names(sigs) <- manifest$file

# --- land scores: cheap CCF (for alignment) + the random forest (the score) -- #
ok_sig <- function(s) length(s$sig) >= 3 && !all(is.na(s$sig))

land_ccf <- function(fa, fb) {  # cheap — used only to find the land alignment
  sa <- sigs[[fa]]; sb <- sigs[[fb]]
  if (!ok_sig(sa) || !ok_sig(sb)) return(NA_real_)
  tryCatch(sig_align(sa$sig, sb$sig)$ccf, error = function(e) NA_real_)
}

land_rf <- function(fa, fb) {  # the bulletxtrctr random-forest matchscore
  sa <- sigs[[fa]]; sb <- sigs[[fb]]
  if (!ok_sig(sa) || !ok_sig(sb)) return(NA_real_)
  tryCatch({
    al <- sig_align(sa$sig, sb$sig)
    feat <- extract_features_all(al, sig_cms_max(al), resolution = sa$resolution)
    as.numeric(predict(rtrees, newdata = feat, type = "prob")[, "TRUE"])
  }, error = function(e) NA_real_)
}

# bullet = (barrel, bullet); ordered land files
manifest$key <- paste(manifest$barrel, manifest$bullet, sep = "_")
bullets <- split(manifest[order(manifest$land), ], manifest$key[order(manifest$land)])
bkeys <- names(bullets)

bullet_score <- function(ba, bb) {
  na <- nrow(ba); nb <- nrow(bb)
  cc <- outer(seq_len(na), seq_len(nb),
              Vectorize(function(i, j) land_ccf(ba$file[i], bb$file[j])))
  diagmean <- vapply(0:(nb - 1), function(k)
    mean(vapply(seq_len(na), function(i) cc[i, ((i - 1 + k) %% nb) + 1], numeric(1)), na.rm = TRUE),
    numeric(1))
  if (all(is.na(diagmean))) return(NA_real_)
  kstar <- (0:(nb - 1))[which.max(diagmean)]
  rf <- vapply(seq_len(na),
               function(i) land_rf(ba$file[i], bb$file[((i - 1 + kstar) %% nb) + 1]), numeric(1))
  mean(rf, na.rm = TRUE)
}

rows <- list()
total <- length(bkeys) * (length(bkeys) - 1) / 2
done <- 0
for (i in seq_len(length(bkeys) - 1)) {
  for (j in (i + 1):length(bkeys)) {
    ba <- bullets[[i]]; bb <- bullets[[j]]
    rows[[length(rows) + 1]] <- data.frame(
      barrel_a = ba$barrel[1], bullet_a = ba$bullet[1],
      barrel_b = bb$barrel[1], bullet_b = bb$bullet[1], score = bullet_score(ba, bb))
    done <- done + 1
    if (done %% 25 == 0) cat("  bullet pairs", done, "/", total, "\n")
  }
}
write.csv(do.call(rbind, rows), out_path, row.names = FALSE)
cat("wrote", out_path, "\n")
