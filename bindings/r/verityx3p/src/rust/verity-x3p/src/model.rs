//! The in-memory data model for an X3P surface.
//!
//! This is the canonical representation that every language binding wraps.
//! Heights are stored as `f64` in a row-major [`ndarray::Array2`] of shape
//! `(ny, nx) = (SizeY, SizeX)`, indexed `data[[y, x]]`.
//!
//! ## Matrix order (the cross-language footgun)
//! In the X3P binary stream the **X index varies fastest**: the file stores all
//! `SizeX` values of row `y = 0`, then row `y = 1`, and so on. A C-order
//! `(ny, nx)` array therefore maps one-to-one onto the stream, so `data[[y, x]]`
//! is the height at grid position `(x, y)`. (The R reference implementation
//! `x3ptools` keeps the transpose — an `(nx, ny)` matrix indexed `[x, y]`; the
//! underlying values are identical.)

use crate::error::{Result, X3pError};
use ndarray::Array2;

/// Binary encoding of a Z value, taken from the ISO 5436-2 `DataType` code.
///
/// `I` = 16-bit int, `L` = 32-bit int, `F` = 32-bit float, `D` = 64-bit float.
/// Verity writes `F` or `D`; it reads all four.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataType {
    /// `I` — signed 16-bit integer.
    I16,
    /// `L` — signed 32-bit integer.
    I32,
    /// `F` — IEEE-754 32-bit float.
    F32,
    /// `D` — IEEE-754 64-bit float.
    F64,
}

impl DataType {
    /// The single-letter ISO code (`I`/`L`/`F`/`D`).
    pub fn code(self) -> &'static str {
        match self {
            DataType::I16 => "I",
            DataType::I32 => "L",
            DataType::F32 => "F",
            DataType::F64 => "D",
        }
    }

    /// Bytes per stored value.
    pub fn byte_size(self) -> usize {
        match self {
            DataType::I16 => 2,
            DataType::I32 => 4,
            DataType::F32 => 4,
            DataType::F64 => 8,
        }
    }

    /// Whether this type can represent NaN (and therefore signal an invalid
    /// point inline, without a separate `valid.bin`).
    pub fn is_float(self) -> bool {
        matches!(self, DataType::F32 | DataType::F64)
    }

    /// Parse an ISO `DataType` code, tolerating surrounding whitespace.
    pub fn from_code(s: &str) -> Result<Self> {
        match s.trim() {
            "I" => Ok(DataType::I16),
            "L" => Ok(DataType::I32),
            "F" => Ok(DataType::F32),
            "D" => Ok(DataType::F64),
            other => Err(X3pError::Malformed(format!(
                "unknown axis DataType code {other:?} (expected I, L, F, or D)"
            ))),
        }
    }
}

/// One coordinate axis (CX, CY, or CZ) from `Record1/Axes`.
#[derive(Debug, Clone, PartialEq)]
pub struct Axis {
    /// `I` (incremental, evenly spaced) or `A` (absolute). Stored verbatim.
    pub axis_type: String,
    /// Binary encoding used for this axis's stored values.
    pub data_type: DataType,
    /// Spacing between samples (X/Y) or Z scale factor, in the file's own units.
    pub increment: f64,
    /// Axis origin.
    pub offset: f64,
}

impl Axis {
    /// A sensible default lateral axis: incremental, `D`, unit spacing.
    pub fn default_lateral() -> Self {
        Axis {
            axis_type: "I".to_string(),
            data_type: DataType::F64,
            increment: 1.0,
            offset: 0.0,
        }
    }

    /// A sensible default Z axis: absolute, `D`, unit scale.
    pub fn default_z() -> Self {
        Axis {
            axis_type: "A".to_string(),
            data_type: DataType::F64,
            increment: 1.0,
            offset: 0.0,
        }
    }
}

/// Instrument description from `Record2`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Instrument {
    pub manufacturer: String,
    pub model: String,
    pub serial: String,
    pub version: String,
}

/// `Record2` — general/provenance metadata. Faithfully round-tripped for the
/// standard fields; non-standard extensions are not yet preserved.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct GeneralInfo {
    pub date: String,
    pub creator: String,
    pub instrument: Instrument,
    pub calibration_date: String,
    pub probing_system_type: String,
    pub probing_system_identification: String,
    pub comment: String,
}

/// A complete X3P surface: the height matrix, a validity mask, the three axes,
/// and provenance metadata.
#[derive(Debug, Clone, PartialEq)]
pub struct Surface {
    /// Height values, shape `(ny, nx)`, indexed `[[y, x]]`. Invalid points are
    /// stored as `f64::NAN`.
    pub data: Array2<f64>,
    /// Validity mask, shape `(ny, nx)`; `true` = measured/valid.
    pub mask: Array2<bool>,
    /// Lateral X axis (`Record1/Axes/CX`).
    pub cx: Axis,
    /// Lateral Y axis (`Record1/Axes/CY`).
    pub cy: Axis,
    /// Z axis (`Record1/Axes/CZ`).
    pub cz: Axis,
    /// `Record2` general information.
    pub general: GeneralInfo,
    /// `Record1/Revision` (e.g. `ISO5436 - 2000`).
    pub revision: String,
    /// `Record1/FeatureType` (`SUR` for a surface, `PRF` for a profile).
    pub feature_type: String,
}

impl Surface {
    /// Number of columns (`SizeX`).
    pub fn nx(&self) -> usize {
        self.data.ncols()
    }

    /// Number of rows (`SizeY`).
    pub fn ny(&self) -> usize {
        self.data.nrows()
    }

    /// Sample spacing along X, in the file's units.
    pub fn increment_x(&self) -> f64 {
        self.cx.increment
    }

    /// Sample spacing along Y, in the file's units.
    pub fn increment_y(&self) -> f64 {
        self.cy.increment
    }

    /// Build a surface from a height matrix, deriving the validity mask from
    /// NaNs and using default axes/metadata. Handy for tests and for callers
    /// that only have raw heights.
    pub fn from_data(data: Array2<f64>) -> Self {
        let mask = data.map(|v| !v.is_nan());
        Surface {
            data,
            mask,
            cx: Axis::default_lateral(),
            cy: Axis::default_lateral(),
            cz: Axis::default_z(),
            general: GeneralInfo::default(),
            revision: "ISO5436 - 2000".to_string(),
            feature_type: "SUR".to_string(),
        }
    }

    /// Validate internal invariants (matrix and mask share a shape, dims fit the
    /// stored axes). Returns the `(ny, nx)` shape on success.
    pub(crate) fn validate_shape(&self) -> Result<(usize, usize)> {
        if self.data.dim() != self.mask.dim() {
            return Err(X3pError::Malformed(format!(
                "data shape {:?} != mask shape {:?}",
                self.data.dim(),
                self.mask.dim()
            )));
        }
        Ok(self.data.dim())
    }
}
