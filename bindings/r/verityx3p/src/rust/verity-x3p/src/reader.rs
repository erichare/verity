//! Reading X3P files into a [`Surface`].

use crate::error::{Result, X3pError};
use crate::model::{DataType, Surface};
use crate::xml::{self, ParsedMeta};
use md5::{Digest, Md5};
use ndarray::Array2;
use std::io::{Cursor, Read, Seek};
use std::path::Path;

/// Options controlling how an X3P file is read.
#[derive(Debug, Clone)]
pub struct ReadOptions {
    /// Verify the stored MD5 of `bindata/data.bin` against the bytes on disk.
    /// On for forensic integrity; turn off only to recover known-corrupt files.
    pub verify_checksums: bool,
}

impl Default for ReadOptions {
    fn default() -> Self {
        ReadOptions {
            verify_checksums: true,
        }
    }
}

/// Read an X3P file from a path with default options.
pub fn read_x3p<P: AsRef<Path>>(path: P) -> Result<Surface> {
    read_x3p_with(path, &ReadOptions::default())
}

/// Read an X3P file from a path with explicit options.
pub fn read_x3p_with<P: AsRef<Path>>(path: P, opts: &ReadOptions) -> Result<Surface> {
    let file = std::fs::File::open(path)?;
    read_x3p_reader(file, opts)
}

/// Read an X3P file from in-memory bytes (used by the language bindings).
pub fn read_x3p_bytes(bytes: &[u8], opts: &ReadOptions) -> Result<Surface> {
    read_x3p_reader(Cursor::new(bytes), opts)
}

/// Raw members pulled out of the zip container.
struct Members {
    main_xml: String,
    data_bin: Vec<u8>,
}

/// Locate and extract the X3P members from the archive. X3P entries may sit at
/// the archive root or under a wrapping folder, so we match by path suffix.
fn extract_members<R: Read + Seek>(reader: R) -> Result<Members> {
    let mut archive = zip::ZipArchive::new(reader)?;
    let mut main_xml: Option<String> = None;
    let mut data_bin: Option<Vec<u8>> = None;

    for i in 0..archive.len() {
        let mut entry = archive.by_index(i)?;
        let name = entry.name().to_string();
        if name.ends_with('/') {
            continue; // directory entry
        }
        if name.ends_with("main.xml") {
            let mut s = String::new();
            entry.read_to_string(&mut s)?;
            main_xml = Some(s);
        } else if name.ends_with("data.bin") {
            let mut b = Vec::with_capacity(entry.size() as usize);
            entry.read_to_end(&mut b)?;
            data_bin = Some(b);
        }
        // valid.bin / mask.png are not yet consumed (see decode notes).
    }

    Ok(Members {
        main_xml: main_xml
            .ok_or_else(|| X3pError::Malformed("no main.xml in archive".to_string()))?,
        data_bin: data_bin
            .ok_or_else(|| X3pError::Malformed("no bindata/data.bin in archive".to_string()))?,
    })
}

/// Upper-case MD5 hex digest of `bytes`.
fn md5_hex(bytes: &[u8]) -> String {
    let digest = Md5::digest(bytes);
    let mut s = String::with_capacity(32);
    for byte in digest {
        s.push_str(&format!("{byte:02X}"));
    }
    s
}

/// Decode the binary Z stream into a row-major `(ny, nx)` height matrix.
///
/// The stream is X-fastest, so the natural C-order fill of an `(ny, nx)` array
/// places `data[[y, x]]` at grid position `(x, y)`. Integer encodings are
/// rescaled by the Z axis (`value * increment + offset`); float encodings are
/// taken verbatim (matching the `x3ptools` reference), with NaN marking invalid
/// points.
fn decode_z(bytes: &[u8], meta: &ParsedMeta) -> Result<(Array2<f64>, Array2<bool>)> {
    let nx = meta.size_x;
    let ny = meta.size_y;
    let n = nx
        .checked_mul(ny)
        .ok_or_else(|| X3pError::Malformed("SizeX * SizeY overflows".to_string()))?;
    let dtype = meta.cz.data_type;
    let bs = dtype.byte_size();

    let needed = n * bs;
    if bytes.len() < needed {
        return Err(X3pError::Malformed(format!(
            "data.bin too short: have {} bytes, need {} ({} points x {} bytes)",
            bytes.len(),
            needed,
            n,
            bs
        )));
    }

    let inc = meta.cz.increment;
    let off = meta.cz.offset;
    let mut heights = Vec::with_capacity(n);
    let mut valid = Vec::with_capacity(n);

    for i in 0..n {
        let p = i * bs;
        let v = match dtype {
            DataType::F32 => f32::from_le_bytes(bytes[p..p + 4].try_into().unwrap()) as f64,
            DataType::F64 => f64::from_le_bytes(bytes[p..p + 8].try_into().unwrap()),
            DataType::I16 => {
                i16::from_le_bytes(bytes[p..p + 2].try_into().unwrap()) as f64 * inc + off
            }
            DataType::I32 => {
                i32::from_le_bytes(bytes[p..p + 4].try_into().unwrap()) as f64 * inc + off
            }
        };
        valid.push(!v.is_nan());
        heights.push(v);
    }

    let data = Array2::from_shape_vec((ny, nx), heights)
        .map_err(|e| X3pError::Malformed(format!("cannot shape data into {ny}x{nx}: {e}")))?;
    let mask = Array2::from_shape_vec((ny, nx), valid)
        .map_err(|e| X3pError::Malformed(format!("cannot shape mask into {ny}x{nx}: {e}")))?;
    Ok((data, mask))
}

/// Core read path shared by the path/bytes entry points.
fn read_x3p_reader<R: Read + Seek>(reader: R, opts: &ReadOptions) -> Result<Surface> {
    let members = extract_members(reader)?;
    let meta = xml::parse_main_xml(&members.main_xml)?;

    if meta.size_z != 1 {
        return Err(X3pError::Unsupported(format!(
            "SizeZ = {} (only areal surfaces with SizeZ = 1 are supported)",
            meta.size_z
        )));
    }

    if opts.verify_checksums {
        if let Some(expected) = &meta.md5_point_data {
            let actual = md5_hex(&members.data_bin);
            if &actual != expected {
                return Err(X3pError::Checksum {
                    what: "bindata/data.bin".to_string(),
                    expected: expected.clone(),
                    actual,
                });
            }
        }
    }

    let (data, mask) = decode_z(&members.data_bin, &meta)?;

    Ok(Surface {
        data,
        mask,
        cx: meta.cx,
        cy: meta.cy,
        cz: meta.cz,
        general: meta.general,
        revision: meta.revision,
        feature_type: meta.feature_type,
    })
}
