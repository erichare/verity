//! Error types for X3P reading and writing.

use thiserror::Error;

/// Anything that can go wrong while reading or writing an X3P file.
#[derive(Debug, Error)]
pub enum X3pError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("zip archive error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("XML parse error: {0}")]
    Xml(#[from] roxmltree::Error),

    /// The archive is structurally valid but violates the X3P schema
    /// (missing `main.xml`, missing `data.bin`, bad dimensions, short buffer, ...).
    #[error("malformed X3P: {0}")]
    Malformed(String),

    /// A well-formed X3P using a feature this codec does not (yet) support.
    #[error("unsupported X3P feature: {0}")]
    Unsupported(String),

    /// A stored MD5 checksum did not match the bytes it covers.
    #[error("checksum mismatch for {what}: expected {expected}, computed {actual}")]
    Checksum {
        what: String,
        expected: String,
        actual: String,
    },
}

/// Convenience alias used throughout the crate.
pub type Result<T> = std::result::Result<T, X3pError>;
