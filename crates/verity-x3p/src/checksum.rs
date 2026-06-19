//! Shared MD5 hex-digest helper used by both the reader (checksum verification)
//! and the writer (emitting the `md5checksum.hex` / point-data checksum).
//!
//! The X3P spec writes the point-data checksum in upper-case (matching the ISO
//! template) and the `md5checksum.hex` file's `main.xml` digest in lower-case;
//! readers compare case-insensitively. One helper serves both.

use md5::{Digest, Md5};

/// Hex MD5 digest of `bytes`. `upper` selects the case of the hex digits.
pub(crate) fn md5_hex(bytes: &[u8], upper: bool) -> String {
    let digest = Md5::digest(bytes);
    let mut s = String::with_capacity(32);
    if upper {
        for byte in digest {
            s.push_str(&format!("{byte:02X}"));
        }
    } else {
        for byte in digest {
            s.push_str(&format!("{byte:02x}"));
        }
    }
    s
}
