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
