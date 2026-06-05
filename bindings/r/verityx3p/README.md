# verityx3p (R)

R binding to the [Verity](https://github.com/erichare/verity) native X3P
(ISO 25178-72) reader/writer, via [extendr](https://extendr.github.io/).
Backed by the `verity-x3p` Rust core, so files round-trip bit-identically with
every other Verity language binding.

```r
# Build-time dependency: install.packages("rextendr")
# Install from the monorepo:  R CMD INSTALL bindings/r/verityx3p

library(verityx3p)
s <- read_x3p(system.file("extdata", "csafe-logo.x3p", package = "verityx3p"))
s
#> <verity_x3p> 741 x 419  (z_type = D)
#>   increments: x = 6.45e-07, y = 6.45e-07
#>   creator: Heike Hofmann, CSAFE

dim(s$surface)                       # nx-by-ny matrix (x3ptools convention)
write_x3p(s, tempfile(fileext = ".x3p"))
```

`s$surface` is an `nx`-by-`ny` numeric matrix (invalid points `NaN`), matching
the `x3ptools` layout; `s$mask` is the matching logical validity matrix.
Building requires a Rust toolchain.
