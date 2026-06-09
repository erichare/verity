#' Verity API client (R) — calibrated, reproducible likelihood ratios.
#'
#' Thin httr2 wrappers over the Verity REST API. Every comparison returns a reproducible
#' `recipe` and a content `handle`; re-running the same inputs reproduces the handle, so
#' verifying a published likelihood ratio is a hash-equality check. The forensic-stats
#' workflow lives in R, so this mirrors the Python client function-for-function.
#'
#' Requires: httr2, curl, jsonlite. Set VERITY_API_URL to point at a deployment
#' (defaults to https://api.verity.codes). See clients/README.md for examples.

verity_base <- function() Sys.getenv("VERITY_API_URL", unset = "https://api.verity.codes")

.verity_perform <- function(req) {
  httr2::resp_body_json(httr2::req_perform(req), simplifyVector = FALSE)
}

verity_get <- function(path, base = verity_base()) {
  .verity_perform(httr2::request(paste0(base, path)))
}

#' Service health + calibrated domains.
verity_health <- function(base = verity_base()) verity_get("/health", base)

#' The deployed scorer hyperparameters + config_hash.
verity_scorer_config <- function(base = verity_base()) verity_get("/v1/scorer-config", base)

#' Every calibration reference + its provenance (scorer hash, datasets, diagnostics).
verity_references <- function(base = verity_base()) verity_get("/v1/references", base)$references

#' Append repeated multipart file fields (one per land), preserving the field name.
.verity_with_files <- function(parts, field, paths) {
  for (p in paths) parts <- c(parts, stats::setNames(list(curl::form_file(p)), field))
  parts
}

#' Compare two marks -> the calibrated report (with the reproducible recipe + handle).
#' `mark_a` / `mark_b` are file paths (a single path, or a character vector of land paths).
#' `scorer_config` is an optional named list of overrides; if its hash does not match the
#' reference's, the API returns the raw score with `calibrated = FALSE` (the firewall).
verity_compare <- function(domain, mark_a, mark_b,
                           include = "calibration,recipe", scorer_config = NULL,
                           base = verity_base()) {
  parts <- list(domain = domain, include = include)
  if (!is.null(scorer_config)) {
    parts$scorer_config <- jsonlite::toJSON(scorer_config, auto_unbox = TRUE)
  }
  parts <- .verity_with_files(parts, "mark_a", mark_a)
  parts <- .verity_with_files(parts, "mark_b", mark_b)
  req <- httr2::req_body_multipart(httr2::request(paste0(base, "/v1/compare")), !!!parts)
  .verity_perform(req)
}

#' Map a score to a bounded LR against a reference (the calibration-firewall step).
verity_calibrate <- function(score, reference, scorer_config_hash = NULL, ci = TRUE,
                             base = verity_base()) {
  parts <- list(score = as.character(score), reference = reference,
                ci = tolower(as.character(ci)))
  if (!is.null(scorer_config_hash)) parts$scorer_config_hash <- scorer_config_hash
  req <- httr2::req_body_multipart(
    httr2::request(paste0(base, "/v1/steps/calibrate")), !!!parts
  )
  .verity_perform(req)
}

#' Upload a scan -> a content-addressed surface handle (the step-graph entry point).
verity_upload <- function(scan, base = verity_base()) {
  req <- httr2::req_body_multipart(
    httr2::request(paste0(base, "/v1/artifacts")), scan = curl::form_file(scan)
  )
  .verity_perform(req)$handle
}

#' Run one pipeline step by name, passing inputs as content handles (e.g.
#' verity_step("areal-signature", surface = h)).
verity_step <- function(name, ..., base = verity_base()) {
  parts <- lapply(list(...), as.character)
  req <- httr2::req_body_multipart(
    httr2::request(paste0(base, "/v1/steps/", name)), !!!parts
  )
  .verity_perform(req)
}
