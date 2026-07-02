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
- Path and in-memory byte-slice APIs (`read_x3p_bytes`, `write_x3p_to_bytes`).

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
