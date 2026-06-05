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
        creator = s.general.creator,
        comment = s.general.comment
    ))
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
) -> Result<(), Error> {
    let nx = nx as usize;
    let ny = ny as usize;
    if data.len() != nx * ny {
        return Err(Error::Other(format!(
            "data length {} does not equal nx*ny = {}",
            data.len(),
            nx * ny
        )));
    }
    let arr =
        ndarray::Array2::from_shape_vec((ny, nx), data).map_err(|e| Error::Other(e.to_string()))?;
    let mut surface = CoreSurface::from_data(arr);
    if mask.len() == nx * ny {
        let m = ndarray::Array2::from_shape_vec((ny, nx), mask.iter().map(|&v| v != 0).collect())
            .map_err(|e| Error::Other(e.to_string()))?;
        surface.mask = m;
    }
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
