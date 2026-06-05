//! Python binding for the `verity-x3p` native X3P codec.
//!
//! Exposes [`read_x3p`]/[`write_x3p`] and a [`Surface`] class that carries the
//! height matrix and validity mask as NumPy arrays plus the X3P axis/provenance
//! metadata. The matrix↔NumPy boundary is crossed via flat `Vec`s (not ndarray
//! types) so this crate's ndarray version need not match rust-numpy's.

use numpy::{PyArray1, PyArray2, PyArrayMethods, PyReadonlyArray2, PyUntypedArrayMethods};
use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use verity_core::{
    read_x3p_with, write_x3p as core_write, DataType, ReadOptions, Surface as CoreSurface,
    WriteOptions, X3pError,
};

/// Map a core error onto an appropriate Python exception.
fn to_pyerr(e: X3pError) -> PyErr {
    match e {
        X3pError::Io(_) => PyIOError::new_err(e.to_string()),
        other => PyValueError::new_err(other.to_string()),
    }
}

/// Parse the `z_type` argument (`"F"` or `"D"`).
fn parse_z_type(code: &str) -> PyResult<DataType> {
    match code {
        "D" | "d" => Ok(DataType::F64),
        "F" | "f" => Ok(DataType::F32),
        other => Err(PyValueError::new_err(format!(
            "z_type must be 'F' (float32) or 'D' (float64), got {other:?}"
        ))),
    }
}

/// An X3P surface: height matrix + validity mask (as NumPy arrays) and metadata.
#[pyclass(module = "verity_x3p")]
pub struct Surface {
    /// Height matrix, shape `(ny, nx)`, dtype float64; invalid points are NaN.
    #[pyo3(get)]
    data: Py<PyArray2<f64>>,
    /// Validity mask, shape `(ny, nx)`, dtype bool; True = measured/valid.
    #[pyo3(get)]
    mask: Py<PyArray2<bool>>,
    #[pyo3(get)]
    nx: usize,
    #[pyo3(get)]
    ny: usize,
    #[pyo3(get)]
    increment_x: f64,
    #[pyo3(get)]
    increment_y: f64,
    /// Z encoding the file uses/used: `"F"` or `"D"`.
    #[pyo3(get)]
    z_type: String,
    #[pyo3(get)]
    creator: String,
    #[pyo3(get)]
    comment: String,
    #[pyo3(get)]
    manufacturer: String,
    #[pyo3(get)]
    revision: String,
    #[pyo3(get)]
    feature_type: String,
}

/// Build a Python [`Surface`] from a core surface, moving the matrices out as
/// flat NumPy arrays reshaped to `(ny, nx)`.
fn surface_to_py(py: Python<'_>, core: CoreSurface) -> PyResult<Surface> {
    let nx = core.nx();
    let ny = core.ny();
    // `.iter()` yields logical (C / X-fastest) order regardless of memory layout.
    let data_vec: Vec<f64> = core.data.iter().copied().collect();
    let mask_vec: Vec<bool> = core.mask.iter().copied().collect();

    let data = PyArray1::from_vec(py, data_vec).reshape([ny, nx])?.unbind();
    let mask = PyArray1::from_vec(py, mask_vec).reshape([ny, nx])?.unbind();

    Ok(Surface {
        data,
        mask,
        nx,
        ny,
        increment_x: core.increment_x(),
        increment_y: core.increment_y(),
        z_type: core.cz.data_type.code().to_string(),
        creator: core.general.creator,
        comment: core.general.comment,
        manufacturer: core.general.instrument.manufacturer,
        revision: core.revision,
        feature_type: core.feature_type,
    })
}

#[pymethods]
impl Surface {
    /// Construct a surface from a NumPy height matrix.
    ///
    /// `data` is a 2-D float64 array `(ny, nx)`; `mask` (optional) is a matching
    /// bool array — if omitted it is derived from NaNs in `data`.
    #[new]
    #[pyo3(signature = (
        data,
        mask=None,
        increment_x=1.0,
        increment_y=1.0,
        creator=String::new(),
        comment=String::new(),
    ))]
    fn new(
        py: Python<'_>,
        data: PyReadonlyArray2<'_, f64>,
        mask: Option<PyReadonlyArray2<'_, bool>>,
        increment_x: f64,
        increment_y: f64,
        creator: String,
        comment: String,
    ) -> PyResult<Self> {
        let shape = data.shape();
        let (ny, nx) = (shape[0], shape[1]);

        let data_vec: Vec<f64> = data.as_array().iter().copied().collect();
        let mask_vec: Vec<bool> = match &mask {
            Some(m) => {
                if m.shape() != shape {
                    return Err(PyValueError::new_err("mask shape must match data shape"));
                }
                m.as_array().iter().copied().collect()
            }
            None => data_vec.iter().map(|v| !v.is_nan()).collect(),
        };

        let data = PyArray1::from_vec(py, data_vec).reshape([ny, nx])?.unbind();
        let mask = PyArray1::from_vec(py, mask_vec).reshape([ny, nx])?.unbind();

        Ok(Surface {
            data,
            mask,
            nx,
            ny,
            increment_x,
            increment_y,
            z_type: "D".to_string(),
            creator,
            comment,
            manufacturer: String::new(),
            revision: "ISO5436 - 2000".to_string(),
            feature_type: "SUR".to_string(),
        })
    }

    fn __repr__(&self) -> String {
        format!(
            "Surface(nx={}, ny={}, increment_x={}, increment_y={}, z_type='{}')",
            self.nx, self.ny, self.increment_x, self.increment_y, self.z_type
        )
    }
}

/// Rebuild a core [`CoreSurface`] from a Python [`Surface`] for writing.
fn py_to_surface(py: Python<'_>, surface: &Surface) -> PyResult<CoreSurface> {
    let data_arr = surface.data.bind(py).readonly();
    let mask_arr = surface.mask.bind(py).readonly();
    let (ny, nx) = (surface.ny, surface.nx);

    let data_vec: Vec<f64> = data_arr.as_array().iter().copied().collect();
    let mask_vec: Vec<bool> = mask_arr.as_array().iter().copied().collect();

    let data = ndarray::Array2::from_shape_vec((ny, nx), data_vec)
        .map_err(|e| PyValueError::new_err(format!("bad data shape: {e}")))?;
    let mask = ndarray::Array2::from_shape_vec((ny, nx), mask_vec)
        .map_err(|e| PyValueError::new_err(format!("bad mask shape: {e}")))?;

    let mut core = CoreSurface::from_data(data);
    core.mask = mask;
    core.cx.increment = surface.increment_x;
    core.cy.increment = surface.increment_y;
    core.general.creator = surface.creator.clone();
    core.general.comment = surface.comment.clone();
    core.general.instrument.manufacturer = surface.manufacturer.clone();
    core.revision = surface.revision.clone();
    core.feature_type = surface.feature_type.clone();
    Ok(core)
}

/// Read an X3P file into a [`Surface`].
#[pyfunction]
#[pyo3(signature = (path, verify_checksums=true))]
fn read_x3p(py: Python<'_>, path: std::path::PathBuf, verify_checksums: bool) -> PyResult<Surface> {
    let opts = ReadOptions { verify_checksums };
    let core = read_x3p_with(path, &opts).map_err(to_pyerr)?;
    surface_to_py(py, core)
}

/// Write a [`Surface`] to an X3P file. `z_type` is `"D"` (default) or `"F"`.
#[pyfunction]
#[pyo3(signature = (surface, path, z_type="D"))]
fn write_x3p(
    py: Python<'_>,
    surface: &Surface,
    path: std::path::PathBuf,
    z_type: &str,
) -> PyResult<()> {
    let core = py_to_surface(py, surface)?;
    let opts = WriteOptions {
        z_type: parse_z_type(z_type)?,
    };
    core_write(&core, path, &opts).map_err(to_pyerr)
}

/// Native X3P (ISO 25178-72) reader/writer, backed by the Verity Rust core.
#[pymodule]
fn verity_x3p(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Surface>()?;
    m.add_function(wrap_pyfunction!(read_x3p, m)?)?;
    m.add_function(wrap_pyfunction!(write_x3p, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
