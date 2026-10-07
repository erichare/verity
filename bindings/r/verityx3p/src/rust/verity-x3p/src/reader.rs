//! Reading X3P files into a [`Surface`].

use crate::checksum::md5_hex;
use crate::error::{Result, X3pError};
use crate::model::{DataType, Surface};
use crate::xml::{self, ParsedMeta};
use ndarray::Array2;
use std::io::{Cursor, Read, Seek};
use std::path::Path;

/// Options controlling how an X3P file is read.
#[derive(Debug, Clone)]
pub struct ReadOptions {
    /// Verify stored MD5 checksums of point data and any declared validity mask.
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
    meta: ParsedMeta,
    data_bin: Vec<u8>,
    valid_bin: Option<Vec<u8>>,
}

/// Normalize safe archive paths consistently for links and ZIP member names.
fn normalized_member_path(link: &str) -> Result<String> {
    if link.is_empty()
        || link.starts_with('/')
        || link.chars().any(|c| matches!(c, ':' | '\\' | '?' | '#'))
    {
        return Err(X3pError::Malformed(format!(
            "linked member must be a local relative archive path: {link:?}"
        )));
    }
    let mut parts = Vec::new();
    for part in link.split('/') {
        match part {
            "." => {}
            "" | ".." => {
                return Err(X3pError::Malformed(format!(
                    "invalid linked archive path: {link:?}"
                )))
            }
            part => parts.push(part),
        }
    }
    if parts.is_empty() {
        return Err(X3pError::Malformed("empty linked archive path".to_string()));
    }
    Ok(parts.join("/"))
}

/// Resolve a local link inside the same archive directory as main.xml. Never
/// interpret links as filesystem paths or network URLs.
fn member_path(main_path: &str, link: &str) -> Result<String> {
    let link = normalized_member_path(link)?;
    let base = main_path.strip_suffix("main.xml").unwrap_or_default();
    normalized_member_path(&format!("{base}{link}"))
}

fn open_member<'a, R: Read + Seek>(
    archive: &'a mut zip::ZipArchive<R>,
    path: &str,
) -> Result<zip::read::ZipFile<'a>> {
    let name = {
        let mut matches = archive
            .file_names()
            .filter(|name| normalized_member_path(name).is_ok_and(|normalized| normalized == path));
        let name = matches.next().ok_or_else(|| {
            X3pError::Malformed(format!("missing linked archive member {path:?}"))
        })?;
        if matches.next().is_some() {
            return Err(X3pError::Malformed(format!(
                "ambiguous linked archive member {path:?}"
            )));
        }
        name.to_owned()
    };
    Ok(archive.by_name(&name)?)
}

fn read_member<R: Read + Seek>(archive: &mut zip::ZipArchive<R>, path: &str) -> Result<Vec<u8>> {
    let mut entry = open_member(archive, path)?;
    let mut bytes = Vec::new();
    entry.read_to_end(&mut bytes)?;
    Ok(bytes)
}

fn read_validity_member<R: Read + Seek>(
    archive: &mut zip::ZipArchive<R>,
    path: &str,
    expected: usize,
) -> Result<Vec<u8>> {
    let entry = open_member(archive, path)?;
    if entry.size() != expected as u64 {
        return Err(X3pError::Malformed(format!(
            "validity mask length is {} bytes, expected {expected}",
            entry.size()
        )));
    }
    // Do not trust the central directory's size. A forged size must not allow
    // the decompressed stream to grow beyond one byte over the expected mask.
    // ceil(point_count / 8) + 1 is representable even at usize::MAX points.
    let mut bytes = Vec::new();
    entry.take(expected as u64 + 1).read_to_end(&mut bytes)?;
    if bytes.len() != expected {
        return Err(X3pError::Malformed(format!(
            "validity mask length is {} bytes, expected {expected}",
            bytes.len()
        )));
    }
    Ok(bytes)
}

fn point_data_size(meta: &ParsedMeta) -> Result<(usize, usize)> {
    let n = meta
        .size_x
        .checked_mul(meta.size_y)
        .ok_or_else(|| X3pError::Malformed("SizeX * SizeY overflows".to_string()))?;
    let needed = n
        .checked_mul(meta.cz.data_type.byte_size())
        .ok_or_else(|| X3pError::Malformed("point count * data type size overflows".to_string()))?;
    Ok((n, needed))
}

fn validate_point_data_length(actual: usize, needed: usize) -> Result<()> {
    if actual < needed {
        return Err(X3pError::Malformed(format!(
            "data.bin too short: have {actual} bytes, need {needed}"
        )));
    }
    Ok(())
}

/// Locate a unique main.xml and read its declared links, including wrapped
/// archives. Exact paths avoid substituting unrelated files with equal suffixes.
fn extract_members<R: Read + Seek>(reader: R) -> Result<Members> {
    let mut archive = zip::ZipArchive::new(reader)?;
    let main_paths: Vec<_> = archive
        .file_names()
        .filter(|name| name.rsplit('/').next() == Some("main.xml"))
        .map(str::to_owned)
        .collect();
    let main_path = match main_paths.as_slice() {
        [path] => path,
        [] => return Err(X3pError::Malformed("no main.xml in archive".to_string())),
        _ => {
            return Err(X3pError::Malformed(
                "multiple main.xml files in archive".to_string(),
            ))
        }
    };
    let mut main_xml = String::new();
    archive.by_name(main_path)?.read_to_string(&mut main_xml)?;
    let meta = xml::parse_main_xml(&main_xml)?;
    let (n, needed) = point_data_size(&meta)?;
    let data_bin = read_member(
        &mut archive,
        &member_path(main_path, &meta.point_data_link)?,
    )?;
    // Inflated dimensions cannot justify a huge mask when point data is short.
    validate_point_data_length(data_bin.len(), needed)?;
    let valid_bin = meta
        .validity
        .as_ref()
        .map(|link| {
            read_validity_member(
                &mut archive,
                &member_path(main_path, &link.path)?,
                n / 8 + usize::from(n % 8 != 0),
            )
        })
        .transpose()?;
    Ok(Members {
        meta,
        data_bin,
        valid_bin,
    })
}

/// Decode the binary Z stream into a row-major `(ny, nx)` height matrix.
///
/// The stream is X-fastest, so the natural C-order fill of an `(ny, nx)` array
/// places `data[[y, x]]` at grid position `(x, y)`. Integer encodings are
/// rescaled by the Z axis (`value * increment + offset`); float encodings are
/// taken verbatim (matching the `x3ptools` reference), with NaN marking invalid
/// points.
fn decode_z(
    bytes: &[u8],
    validity: Option<&[u8]>,
    meta: &ParsedMeta,
) -> Result<(Array2<f64>, Array2<bool>)> {
    let nx = meta.size_x;
    let ny = meta.size_y;
    let (n, needed) = point_data_size(meta)?;
    let dtype = meta.cz.data_type;
    let bs = dtype.byte_size();

    validate_point_data_length(bytes.len(), needed)?;
    if let Some(bits) = validity {
        let needed = n / 8 + usize::from(n % 8 != 0);
        if bits.len() != needed {
            return Err(X3pError::Malformed(format!(
                "validity mask length is {} bytes, expected {} for {} points",
                bits.len(),
                needed,
                n
            )));
        }
    }

    let inc = meta.cz.increment;
    let off = meta.cz.offset;
    let mut heights = Vec::with_capacity(n);
    let mut valid = Vec::with_capacity(n);

    for i in 0..n {
        let p = i * bs;
        // The `try_into().unwrap()` is sound: the length check above guarantees
        // `bytes.len() >= n * bs`, so `bytes[p..p+bs]` is always in-bounds and
        // exactly `bs` long for every `i < n`.
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
        // OpenGPS ValidBuffer::IsValid: LSB-first bits, 1 = valid, X-fastest.
        // Unused high bits of the last byte have no associated point. A set
        // mask bit cannot turn a NaN coordinate into a measured height.
        let mask_valid = match validity {
            Some(bits) => bits[i / 8] & (1 << (i % 8)) != 0,
            None => true,
        };
        valid.push(mask_valid && !v.is_nan());
        heights.push(if mask_valid { v } else { f64::NAN });
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
    let meta = members.meta;

    if meta.size_z != 1 {
        return Err(X3pError::Unsupported(format!(
            "SizeZ = {} (only areal surfaces with SizeZ = 1 are supported)",
            meta.size_z
        )));
    }

    if opts.verify_checksums {
        if let Some(expected) = &meta.md5_point_data {
            let actual = md5_hex(&members.data_bin, true);
            if &actual != expected {
                return Err(X3pError::Checksum {
                    what: meta.point_data_link.clone(),
                    expected: expected.clone(),
                    actual,
                });
            }
        }
        if let (Some(link), Some(bytes)) = (&meta.validity, &members.valid_bin) {
            let actual = md5_hex(bytes, true);
            if actual != link.checksum {
                return Err(X3pError::Checksum {
                    what: link.path.clone(),
                    expected: link.checksum.clone(),
                    actual,
                });
            }
        }
    }

    let (data, mask) = decode_z(&members.data_bin, members.valid_bin.as_deref(), &meta)?;

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
