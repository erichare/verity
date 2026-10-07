use extendr_api::prelude::*;
use verity_core::{
    read_x3p_with, write_x3p as core_write, DataType, ReadOptions, Surface as CoreSurface,
    WriteOptions,
};

// Read an X3P file into raw components. Internal FFI shim — the documented R
// API is `read_x3p()` in R/x3p.R, so this carries no roxygen block (a plain
// `//` comment keeps it out of the generated wrappers and the man/ pages).
//
// `data`/`mask` are returned X-fastest, i.e. ordered to fill an `nx`-by-`ny`
// R matrix in column-major order (the `x3ptools` convention).
#[extendr]
fn rust_read_x3p(path: &str, verify_checksums: bool) -> Result<List, Error> {
    let opts = ReadOptions { verify_checksums };
    let s = read_x3p_with(path, &opts).map_err(|e| Error::Other(e.to_string()))?;
    let data: Vec<f64> = s.data.iter().copied().collect();
    let mask: Vec<i32> = s.mask.iter().map(|&b| i32::from(b)).collect();
    Ok(list!(
        data = data,
        mask = mask,
        nx = s.nx() as i32,
        ny = s.ny() as i32,
        increment_x = s.increment_x(),
        increment_y = s.increment_y(),
        z_type = s.cz.data_type.code(),
        creator = s.general.creator.clone(),
        comment = s.general.comment.clone(),
        metadata = list!(
            cx_axis_type = s.cx.axis_type,
            cx_data_type = s.cx.data_type.code(),
            cx_offset = s.cx.offset,
            cy_axis_type = s.cy.axis_type,
            cy_data_type = s.cy.data_type.code(),
            cy_offset = s.cy.offset,
            cz_axis_type = s.cz.axis_type,
            cz_increment = s.cz.increment,
            cz_offset = s.cz.offset,
            revision = s.revision,
            feature_type = s.feature_type,
            date = s.general.date,
            creator = s.general.creator,
            comment = s.general.comment,
            manufacturer = s.general.instrument.manufacturer,
            model = s.general.instrument.model,
            serial = s.general.instrument.serial,
            version = s.general.instrument.version,
            calibration_date = s.general.calibration_date,
            probing_system_type = s.general.probing_system_type,
            probing_system_identification = s.general.probing_system_identification
        )
    ))
}

// Metadata is optional for objects created by callers or older package versions.
// Present values must have the expected scalar type, rather than being lost or
// silently replaced by defaults.
fn apply_metadata(surface: &mut CoreSurface, metadata: List) -> Result<(), Error> {
    for (name, value) in metadata.iter() {
        match name {
            "cx_axis_type" => surface.cx.axis_type = value.try_into()?,
            "cx_data_type" => {
                surface.cx.data_type = DataType::from_code(&String::try_from(value)?)
                    .map_err(|e| Error::Other(e.to_string()))?
            }
            "cx_offset" => surface.cx.offset = value.try_into()?,
            "cy_axis_type" => surface.cy.axis_type = value.try_into()?,
            "cy_data_type" => {
                surface.cy.data_type = DataType::from_code(&String::try_from(value)?)
                    .map_err(|e| Error::Other(e.to_string()))?
            }
            "cy_offset" => surface.cy.offset = value.try_into()?,
            "cz_axis_type" => surface.cz.axis_type = value.try_into()?,
            "cz_increment" => surface.cz.increment = value.try_into()?,
            "cz_offset" => surface.cz.offset = value.try_into()?,
            "revision" => surface.revision = value.try_into()?,
            "feature_type" => surface.feature_type = value.try_into()?,
            "date" => surface.general.date = value.try_into()?,
            "creator" => surface.general.creator = value.try_into()?,
            "comment" => surface.general.comment = value.try_into()?,
            "manufacturer" => surface.general.instrument.manufacturer = value.try_into()?,
            "model" => surface.general.instrument.model = value.try_into()?,
            "serial" => surface.general.instrument.serial = value.try_into()?,
            "version" => surface.general.instrument.version = value.try_into()?,
            "calibration_date" => surface.general.calibration_date = value.try_into()?,
            "probing_system_type" => surface.general.probing_system_type = value.try_into()?,
            "probing_system_identification" => {
                surface.general.probing_system_identification = value.try_into()?
            }
            _ => return Err(Error::Other(format!("unknown metadata field: {name}"))),
        }
    }
    Ok(())
}

// Write raw components to an X3P file. Internal FFI shim for `write_x3p()` in
// R/x3p.R (no roxygen block, by design). `data` is X-fastest (column-major from
// an `nx`-by-`ny` matrix); `z_type` is `"D"` (float64) or `"F"` (float32).
#[extendr]
fn rust_write_x3p(
    path: &str,
    data: Vec<f64>,
    mask: Vec<i32>,
    nx: i32,
    ny: i32,
    increment_x: f64,
    increment_y: f64,
    z_type: &str,
    metadata: List,
) -> Result<(), Error> {
    let nx = usize::try_from(nx).map_err(|_| Error::Other("nx must be nonnegative".into()))?;
    let ny = usize::try_from(ny).map_err(|_| Error::Other("ny must be nonnegative".into()))?;
    let count = nx
        .checked_mul(ny)
        .ok_or_else(|| Error::Other("nx*ny overflows".into()))?;
    if data.len() != count {
        return Err(Error::Other(format!(
            "data length {} does not equal nx*ny = {}",
            data.len(),
            count
        )));
    }
    let arr =
        ndarray::Array2::from_shape_vec((ny, nx), data).map_err(|e| Error::Other(e.to_string()))?;
    let mut surface = CoreSurface::from_data(arr);
    if !mask.is_empty() && mask.len() != count {
        return Err(Error::Other("mask length must match data length".into()));
    }
    if mask.len() == count {
        let m = ndarray::Array2::from_shape_vec((ny, nx), mask.iter().map(|&v| v != 0).collect())
            .map_err(|e| Error::Other(e.to_string()))?;
        surface.mask = m;
    }
    apply_metadata(&mut surface, metadata)?;
    surface.cx.increment = increment_x;
    surface.cy.increment = increment_y;
    let z = match z_type {
        "F" | "f" => DataType::F32,
        _ => DataType::F64,
    };
    core_write(&surface, path, &WriteOptions { z_type: z }).map_err(|e| Error::Other(e.to_string()))
}

// Macro to generate exports.
extendr_module! {
    mod verityx3p;
    fn rust_read_x3p;
    fn rust_write_x3p;
}
