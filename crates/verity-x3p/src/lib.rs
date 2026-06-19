//! # verity-x3p
//!
//! A native, dependency-light reader and writer for the **X3P** surface
//! topography format (ISO 25178-72 / ISO 5436-2) — the standard container for
//! 3D forensic surface scans (bullet lands, breech-face impressions, toolmarks,
//! footwear, fractured surfaces).
//!
//! An X3P file is a zip/OPC container holding a `main.xml` metadata document and
//! a `bindata/data.bin` matrix of Z heights. This crate is the single source of
//! truth for the [Verity](https://github.com/erichare/verity) project's X3P I/O;
//! every language binding (Python, R, TypeScript, …) wraps it so that a file
//! written from one language reads back bit-identically in every other.
//!
//! ```no_run
//! use verity_x3p::{read_x3p, write_x3p, WriteOptions};
//!
//! let surface = read_x3p("scan.x3p")?;
//! println!("{} x {} points", surface.nx(), surface.ny());
//! write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;
//! # Ok::<(), verity_x3p::X3pError>(())
//! ```

mod checksum;
mod error;
mod model;
mod reader;
mod writer;
mod xml;

pub use error::{Result, X3pError};
pub use model::{Axis, DataType, GeneralInfo, Instrument, Surface};
pub use reader::{read_x3p, read_x3p_bytes, read_x3p_with, ReadOptions};
pub use writer::{write_x3p, write_x3p_to_bytes, WriteOptions};
