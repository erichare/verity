# Verity

**An open, domain-general engine for forensic surface comparison.**

Verity compares 3D surface-topography scans — bullet lands, cartridge-case
breech-face impressions, striated and impressed toolmarks, footwear, fractured
surfaces — directly from [X3P](https://www.iso.org/standard/62395.html) files
(ISO 25178-72). It pairs a learned, domain-general surface representation with a
**transparent, calibrated likelihood-ratio decision layer** and region-level
attribution. The machine never reports a "match"; it reports an *auditable weight
of evidence*, with performance characterized on a named dataset.

> **Status: early.** The first foundational piece — `verity-x3p`, a native X3P
> reader/writer — has landed and is tested against real-world files. The
> comparison method and platform are in active design (see the project plan).

## Why

Forensic firearm/toolmark comparison today is either subjective examiner
judgment or proprietary black-box correlation (IBIS), while the open tooling is a
pile of *domain-specific* R packages with no unified, deployable platform. Courts
are increasingly skeptical of unqualified pattern-match testimony (e.g.
*Abruquah v. Maryland*, 2023; the 2023 amendment to FRE 702), and no discipline
yet has a well-characterized error rate. Verity's bet: **one general, calibrated,
explainable method** — proven first where ground truth is strongest (firearms),
then transferred across domains.

Design principles:

- **Statistics decide, not a black box.** A learned representation produces a
  score; a transparent, calibrated likelihood ratio turns that score into a
  reportable weight of evidence. AI assists with the work *around* the decision
  (preprocessing, QC, documentation), never the decision itself.
- **Reproducible by construction.** Deterministic, version-pinned, content-hashed.
- **Open and language-independent.** Built on the X3P standard, MIT/Apache-2.0.

## Architecture

- **`crates/verity-x3p`** — a native Rust reader/writer for X3P (ISO 25178-72).
  It is the single source of truth for the format; thin per-language bindings
  (Python via PyO3 first, then R / TypeScript / Swift / Java) wrap this one core
  so a file written from any language reads back *bit-identically* in every
  other. Licensed `MIT OR Apache-2.0`.
- **`verity` (planned)** — the Python science stack: surface-metrology
  preprocessing (ISO 16610 S/L/F filtering), registration, the hybrid
  representation + calibrated LR, and the validation harness.

## `verity-x3p`

```rust
use verity_x3p::{read_x3p, write_x3p, WriteOptions};

let surface = read_x3p("scan.x3p")?;          // verifies the stored MD5
println!("{} x {} points", surface.nx(), surface.ny());
write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;
# Ok::<(), verity_x3p::X3pError>(())
```

Heights are an `ndarray` `(ny, nx)` matrix of `f64` (invalid points are NaN), with
a parallel validity mask and the X3P axis/provenance metadata. Reads `I`/`L`/`F`/`D`
encodings; writes `F`/`D`. Run the tests:

```bash
cargo test -p verity-x3p
```

## License

`MIT OR Apache-2.0`, at your option.
