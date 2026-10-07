test_that("reads the bundled csafe-logo fixture", {
  path <- system.file("extdata", "csafe-logo.x3p", package = "verityx3p")
  skip_if(path == "", "fixture not installed")
  s <- read_x3p(path)
  expect_s3_class(s, "verity_x3p")
  expect_identical(c(s$nx, s$ny), c(741L, 419L))
  expect_identical(dim(s$surface), c(741L, 419L))
  expect_identical(s$z_type, "D")
  expect_gt(sum(s$mask), 0)
})

test_that("write/read round-trips a synthetic surface", {
  m <- matrix(as.double(1:12), nrow = 4, ncol = 3) # nx = 4, ny = 3
  m[2, 2] <- NaN
  x <- structure(
    list(
      surface = m, mask = !is.na(m), nx = 4L, ny = 3L,
      increment_x = 1.5625, increment_y = 2.0,
      z_type = "D", creator = "test", comment = ""
    ),
    class = "verity_x3p"
  )
  tmp <- tempfile(fileext = ".x3p")
  on.exit(unlink(tmp), add = TRUE)
  write_x3p(x, tmp)
  y <- read_x3p(tmp)
  expect_identical(dim(y$surface), c(4L, 3L))
  expect_equal(y$surface, x$surface)
  expect_true(is.na(y$surface[2, 2]))
  expect_false(y$mask[2, 2])
  expect_equal(y$increment_x, 1.5625)
  expect_equal(y$increment_y, 2.0)
  expect_identical(y$creator, "test")
})

test_that("standard metadata survives read and write", {
  path <- system.file("extdata", "csafe-logo.x3p", package = "verityx3p")
  skip_if(path == "", "fixture not installed")
  x <- read_x3p(path)
  x$metadata$cx_offset <- 0.125
  x$metadata$cy_offset <- -0.5
  x$metadata$cz_increment <- 0.25
  x$metadata$cz_offset <- 1.5
  x$metadata$model <- "Instrument & <model>"
  x$metadata$serial <- "Serial 123"
  x$creator <- "Updated creator"
  x$comment <- "Updated comment"
  tmp <- tempfile(fileext = ".x3p")
  on.exit(unlink(tmp), add = TRUE)
  write_x3p(x, tmp)
  y <- read_x3p(tmp)
  expected <- x$metadata
  expected$creator <- x$creator
  expected$comment <- x$comment
  expect_identical(y$metadata, expected)
  expect_identical(y$creator, x$creator)
  expect_identical(y$comment, x$comment)
  expect_equal(y$surface, x$surface)
})

test_that("invalid dimensions and mask lengths are rejected", {
  path <- system.file("extdata", "csafe-logo.x3p", package = "verityx3p")
  skip_if(path == "", "fixture not installed")
  x <- read_x3p(path)
  tmp <- tempfile(fileext = ".x3p")
  on.exit(unlink(tmp), add = TRUE)
  bad <- x
  bad$nx <- -1L
  expect_error(write_x3p(bad, tmp), "nx must be nonnegative")
  bad <- x
  bad$mask <- TRUE
  expect_error(write_x3p(bad, tmp), "mask length must match")
})

test_that("checksum verification rejects corruption", {
  path <- system.file("extdata", "csafe-logo.x3p", package = "verityx3p")
  skip_if(path == "", "fixture not installed")
  raw <- readBin(path, "raw", n = file.info(path)$size)
  i <- length(raw) %/% 2L
  raw[i] <- as.raw(bitwXor(as.integer(raw[i]), 255L))
  tmp <- tempfile(fileext = ".x3p")
  on.exit(unlink(tmp), add = TRUE)
  writeBin(raw, tmp)
  expect_error(read_x3p(tmp))
})

test_that("packed validity fixtures preserve X-fastest masks and scaled heights", {
  for (code in c("I", "L", "F", "D")) {
    path <- system.file("extdata", paste0("validity-", tolower(code), ".x3p"), package = "verityx3p")
    expect_true(nzchar(path))
    x <- read_x3p(path)
    expected_mask <- c(TRUE, FALSE, TRUE, FALSE, TRUE, FALSE, FALSE, TRUE, TRUE, FALSE)
    if (code == "I") {
      values <- (-10:-1) * 0.5 + 100
    } else if (code == "L") {
      values <- (100000:100009) * 0.5 + 100
    } else {
      values <- as.double(0:9)
      expected_mask[3] <- FALSE # Its set bit cannot make a NaN coordinate valid.
    }
    values[!expected_mask] <- NaN
    expect_identical(dim(x$surface), c(5L, 2L))
    expect_identical(x$mask, matrix(expected_mask, nrow = 5, ncol = 2))
    expect_equal(x$surface, matrix(values, nrow = 5, ncol = 2))
    tmp <- tempfile(fileext = ".x3p")
    write_x3p(x, tmp)
    y <- read_x3p(tmp)
    unlink(tmp)
    expect_identical(y$mask, x$mask)
    expect_equal(y$surface, x$surface)
  }
})
