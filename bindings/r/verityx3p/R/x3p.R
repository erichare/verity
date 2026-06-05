#' Read an X3P surface scan
#'
#' Reads an X3P (ISO 25178-72) 3D surface-topography file via the Verity Rust
#' core.
#'
#' @param path Path to an `.x3p` file.
#' @param verify_checksums Verify the stored MD5 of the data matrix (default `TRUE`).
#' @return A `verity_x3p` object: a list with `surface` (an `nx`-by-`ny` numeric
#'   matrix, invalid points `NaN`), `mask` (logical matrix), `nx`, `ny`,
#'   `increment_x`, `increment_y`, `z_type`, `creator`, and `comment`.
#' @export
read_x3p <- function(path, verify_checksums = TRUE) {
  res <- rust_read_x3p(path.expand(path), isTRUE(verify_checksums))
  surface <- matrix(res$data, nrow = res$nx, ncol = res$ny)
  mask <- matrix(as.logical(res$mask), nrow = res$nx, ncol = res$ny)
  structure(
    list(
      surface = surface,
      mask = mask,
      nx = res$nx,
      ny = res$ny,
      increment_x = res$increment_x,
      increment_y = res$increment_y,
      z_type = res$z_type,
      creator = res$creator,
      comment = res$comment
    ),
    class = "verity_x3p"
  )
}

#' Write an X3P surface scan
#'
#' @param x A `verity_x3p` object (e.g. from [read_x3p()]).
#' @param path Output path.
#' @param z_type Binary encoding: `"D"` (float64, default) or `"F"` (float32).
#' @return `path`, invisibly.
#' @export
write_x3p <- function(x, path, z_type = c("D", "F")) {
  z_type <- match.arg(z_type)
  stopifnot(inherits(x, "verity_x3p"))
  mask <- if (!is.null(x$mask)) as.integer(x$mask) else integer(0)
  rust_write_x3p(
    path.expand(path),
    as.double(as.vector(x$surface)),
    mask,
    as.integer(x$nx),
    as.integer(x$ny),
    as.double(x$increment_x),
    as.double(x$increment_y),
    z_type
  )
  invisible(path)
}

#' @export
print.verity_x3p <- function(x, ...) {
  cat(sprintf("<verity_x3p> %d x %d  (z_type = %s)\n", x$nx, x$ny, x$z_type))
  cat(sprintf("  increments: x = %g, y = %g\n", x$increment_x, x$increment_y))
  if (nzchar(x$creator)) cat(sprintf("  creator: %s\n", x$creator))
  invisible(x)
}
