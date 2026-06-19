//! Writing a [`Surface`] back out as a spec-conforming X3P file.

use crate::checksum::md5_hex;
use crate::error::{Result, X3pError};
use crate::model::{DataType, Surface};
use crate::xml;
use std::io::{Cursor, Write};
use std::path::Path;

/// Options controlling how an X3P file is written.
#[derive(Debug, Clone)]
pub struct WriteOptions {
    /// Binary encoding for Z values. Only the float types (`F`/`D`) are
    /// supported on write, because they can represent invalid points inline as
    /// NaN. Defaults to `D` (64-bit), matching the `x3ptools` default.
    pub z_type: DataType,
}

impl Default for WriteOptions {
    fn default() -> Self {
        WriteOptions {
            z_type: DataType::F64,
        }
    }
}

/// Encode the height matrix into the X3P binary stream (X-fastest), writing NaN
/// for any point the mask marks invalid.
fn encode_z(surface: &Surface, z_type: DataType) -> Result<Vec<u8>> {
    if !z_type.is_float() {
        return Err(X3pError::Unsupported(format!(
            "writing integer Z type {} is not supported; use F or D",
            z_type.code()
        )));
    }
    let (ny, nx) = surface.validate_shape()?;
    let mut out = Vec::with_capacity(ny * nx * z_type.byte_size());
    // ndarray iterates a standard array in C order (row y outer, col x inner),
    // i.e. X-fastest — exactly the X3P stream order.
    for (height, &valid) in surface.data.iter().zip(surface.mask.iter()) {
        let v = if valid { *height } else { f64::NAN };
        match z_type {
            DataType::F32 => out.extend_from_slice(&(v as f32).to_le_bytes()),
            DataType::F64 => out.extend_from_slice(&v.to_le_bytes()),
            _ => unreachable!("guarded by is_float check above"),
        }
    }
    Ok(out)
}

/// Serialize a surface to X3P bytes (an in-memory zip container).
pub fn write_x3p_to_bytes(surface: &Surface, opts: &WriteOptions) -> Result<Vec<u8>> {
    let (ny, nx) = surface.validate_shape()?;

    // 1. Encode the binary matrix and checksum it.
    let data_bin = encode_z(surface, opts.z_type)?;
    // Upper-case to match the ISO template example; readers compare case-insensitively.
    let data_md5 = md5_hex(&data_bin, true);

    // 2. Build main.xml referencing that checksum, then checksum main.xml itself.
    let main_xml = xml::build_main_xml(
        nx,
        ny,
        &surface.cx,
        &surface.cy,
        &surface.cz,
        opts.z_type,
        &surface.general,
        &surface.revision,
        &surface.feature_type,
        &data_md5,
    );
    // Lower-case to match the `md5checksum.hex` convention; readers compare case-insensitively.
    let main_md5 = md5_hex(main_xml.as_bytes(), false);
    let checksum_file = format!("{main_md5}\n");

    // 3. Assemble the zip container.
    let mut cursor = Cursor::new(Vec::new());
    {
        let mut zw = zip::ZipWriter::new(&mut cursor);
        let options = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated);

        zw.start_file("main.xml", options)?;
        zw.write_all(main_xml.as_bytes())?;

        zw.start_file("bindata/data.bin", options)?;
        zw.write_all(&data_bin)?;

        zw.start_file("md5checksum.hex", options)?;
        zw.write_all(checksum_file.as_bytes())?;

        zw.finish()?;
    }
    Ok(cursor.into_inner())
}

/// Write a surface to an X3P file at `path`.
pub fn write_x3p<P: AsRef<Path>>(surface: &Surface, path: P, opts: &WriteOptions) -> Result<()> {
    let bytes = write_x3p_to_bytes(surface, opts)?;
    if let Some(parent) = path.as_ref().parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    std::fs::write(path, bytes)?;
    Ok(())
}
