# verity-x3p

A native, dependency-light Rust reader and writer for the **X3P** surface
topography format (ISO 25178-72 / ISO 5436-2) — the standard container for 3D
forensic surface scans (bullet lands, breech-face impressions, toolmarks,
footwear, fractured surfaces).

An X3P file is a zip/OPC container holding a `main.xml` metadata document and a
`bindata/data.bin` matrix of Z heights. This crate is the single source of
truth for the [Verity](https://github.com/erichare/verity) project's X3P I/O;
every language binding (Python, R, TypeScript, …) wraps it so that a file
written from one language reads back bit-identically in every other.

## Features

- Reads all four ISO Z-data encodings (`I`/`L`/`F`/`D` — int16, int32, f32,
  f64) with the spec's column-major, X-fastest matrix order.
- Verifies the stored MD5 checksum of the point data on read (on by default;
  opt out via `ReadOptions` to recover known-corrupt files) and emits both the
  point-data checksum and `md5checksum.hex` on write.
- Invalid points are surfaced as `NaN` plus an explicit validity mask.
- Reads the declared `ValidPointsLink` packed mask for all four Z encodings,
  verifies `MD5ChecksumValidPoints`, and resolves linked files relative to
  `main.xml`, including archives inside a wrapping folder. Missing or malformed
  mask declarations, missing members, and incorrect mask lengths are errors.
- Path and in-memory byte-slice APIs (`read_x3p_bytes`, `write_x3p_to_bytes`).

The validity mask is X-fastest and least-significant-bit first, with 1 meaning
valid, as implemented by the [openGPS reference library](https://svn.code.sf.net/p/open-gps/code/!svn/bc/402/ISO5436_XML/branches/Kohler_LinuxPort/src/ISO5436_2_XML/cxx/valid_buffer.cxx).
It must contain exactly `ceil(SizeX * SizeY / 8)` bytes. Unused high bits of the
last byte are ignored. A point is valid only when its mask bit is set and its
height is not NaN. With no declared mask, the existing NaN-based behavior applies.
Writers retain the validity semantics by storing masked points as NaN in F/D
output. `verify_checksums=false` skips checksum comparisons for recovery but
does not bypass mask declaration or length validation.

This corrects earlier versions that ignored separately stored masks. Scans with
finite heights marked invalid may therefore produce different downstream scores.
See the [validation impact note](../../docs/headline-numbers.md#codec-validity-mask-change-2026-10-07)
before associating historical validation numbers with the changed decoder.

## Usage

```rust,no_run
use verity_x3p::{read_x3p, write_x3p, WriteOptions, X3pError};

fn main() -> Result<(), X3pError> {
    let surface = read_x3p("scan.x3p")?;
    println!("{} x {} points", surface.nx(), surface.ny());
    write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;
    Ok(())
}
```

## License

Licensed under either of [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)
or [MIT license](https://opensource.org/licenses/MIT) at your option.
