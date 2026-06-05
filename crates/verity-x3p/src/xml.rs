//! Parsing and generation of the X3P `main.xml` metadata document
//! (`p:ISO5436_2`, namespace `http://www.opengps.eu/2008/ISO5436_2`).

use crate::error::{Result, X3pError};
use crate::model::{Axis, DataType, GeneralInfo, Instrument};
use roxmltree::{Document, Node};

/// Everything the reader needs out of `main.xml`.
pub(crate) struct ParsedMeta {
    pub size_x: usize,
    pub size_y: usize,
    pub size_z: usize,
    pub cx: Axis,
    pub cy: Axis,
    pub cz: Axis,
    pub general: GeneralInfo,
    pub revision: String,
    pub feature_type: String,
    /// `Record3/DataLink/MD5ChecksumPointData`, if present (normalized upper-case hex).
    pub md5_point_data: Option<String>,
}

/// Find the first descendant element with the given local name (namespace-agnostic).
fn find<'a>(root: Node<'a, 'a>, name: &str) -> Option<Node<'a, 'a>> {
    root.descendants()
        .find(|n| n.is_element() && n.tag_name().name() == name)
}

/// Trimmed text of the first descendant element with `name`.
fn text(root: Node, name: &str) -> Option<String> {
    find(root, name)
        .and_then(|n| n.text())
        .map(|s| s.trim().to_string())
}

/// Required `usize` field.
fn req_usize(root: Node, name: &str) -> Result<usize> {
    text(root, name)
        .ok_or_else(|| X3pError::Malformed(format!("missing <{name}>")))?
        .parse::<usize>()
        .map_err(|e| X3pError::Malformed(format!("<{name}> is not an integer: {e}")))
}

/// Parse one `<CX>`/`<CY>`/`<CZ>` axis node.
fn parse_axis(axis_node: Node, default_axis_type: &str) -> Result<Axis> {
    let data_type = match text(axis_node, "DataType") {
        Some(code) => DataType::from_code(&code)?,
        None => DataType::F64,
    };
    let axis_type = text(axis_node, "AxisType").unwrap_or_else(|| default_axis_type.to_string());
    let increment = text(axis_node, "Increment")
        .and_then(|s| s.parse::<f64>().ok())
        .unwrap_or(1.0);
    let offset = text(axis_node, "Offset")
        .and_then(|s| s.parse::<f64>().ok())
        .unwrap_or(0.0);
    Ok(Axis {
        axis_type,
        data_type,
        increment,
        offset,
    })
}

/// Parse a full `main.xml` document.
pub(crate) fn parse_main_xml(xml: &str) -> Result<ParsedMeta> {
    let doc = Document::parse(xml)?;
    let root = doc.root_element();

    let cx_node =
        find(root, "CX").ok_or_else(|| X3pError::Malformed("missing <CX> axis".to_string()))?;
    let cy_node =
        find(root, "CY").ok_or_else(|| X3pError::Malformed("missing <CY> axis".to_string()))?;
    let cz = match find(root, "CZ") {
        Some(n) => parse_axis(n, "A")?,
        None => Axis::default_z(),
    };

    let instrument = find(root, "Instrument");
    let probing = find(root, "ProbingSystem");
    let general = GeneralInfo {
        date: text(root, "Date").unwrap_or_default(),
        creator: text(root, "Creator").unwrap_or_default(),
        instrument: Instrument {
            manufacturer: instrument
                .and_then(|n| text(n, "Manufacturer"))
                .unwrap_or_default(),
            model: instrument
                .and_then(|n| text(n, "Model"))
                .unwrap_or_default(),
            serial: instrument
                .and_then(|n| text(n, "Serial"))
                .unwrap_or_default(),
            version: instrument
                .and_then(|n| text(n, "Version"))
                .unwrap_or_default(),
        },
        calibration_date: text(root, "CalibrationDate").unwrap_or_default(),
        probing_system_type: probing.and_then(|n| text(n, "Type")).unwrap_or_default(),
        probing_system_identification: probing
            .and_then(|n| text(n, "Identification"))
            .unwrap_or_default(),
        comment: text(root, "Comment").unwrap_or_default(),
    };

    Ok(ParsedMeta {
        size_x: req_usize(root, "SizeX")?,
        size_y: req_usize(root, "SizeY")?,
        size_z: text(root, "SizeZ")
            .and_then(|s| s.parse().ok())
            .unwrap_or(1),
        cx: parse_axis(cx_node, "I")?,
        cy: parse_axis(cy_node, "I")?,
        cz,
        general,
        revision: text(root, "Revision").unwrap_or_else(|| "ISO5436 - 2000".to_string()),
        feature_type: text(root, "FeatureType").unwrap_or_else(|| "SUR".to_string()),
        md5_point_data: text(root, "MD5ChecksumPointData").map(|s| s.trim().to_uppercase()),
    })
}

/// Escape the five XML predefined entities in element text.
fn esc(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(c),
        }
    }
    out
}

/// Format an axis `<Increment>`/`<Offset>` number. Rust's default `f64` Display
/// emits the shortest decimal string that parses back to the identical `f64`
/// (and never uses scientific notation), so increments like `6.45e-7` m
/// round-trip losslessly while `2.0` still prints as `2`.
fn num(v: f64) -> String {
    format!("{v}")
}

/// Build a spec-conforming `main.xml` for a surface being written.
///
/// `z_type` is the encoding chosen for the binary file (`F` or `D`);
/// `md5_point_data` is the upper-case MD5 hex of `bindata/data.bin`.
#[allow(clippy::too_many_arguments)]
pub(crate) fn build_main_xml(
    nx: usize,
    ny: usize,
    cx: &Axis,
    cy: &Axis,
    cz: &Axis,
    z_type: DataType,
    general: &GeneralInfo,
    revision: &str,
    feature_type: &str,
    md5_point_data: &str,
) -> String {
    let g = general;
    format!(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<p:ISO5436_2 xmlns:p="http://www.opengps.eu/2008/ISO5436_2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengps.eu/2008/ISO5436_2 http://www.opengps.eu/2008/ISO5436_2/ISO5436_2.xsd">
  <Record1>
    <Revision>{revision}</Revision>
    <FeatureType>{feature_type}</FeatureType>
    <Axes>
      <CX>
        <AxisType>{cx_type}</AxisType>
        <DataType>{cx_dt}</DataType>
        <Increment>{cx_inc}</Increment>
        <Offset>{cx_off}</Offset>
      </CX>
      <CY>
        <AxisType>{cy_type}</AxisType>
        <DataType>{cy_dt}</DataType>
        <Increment>{cy_inc}</Increment>
        <Offset>{cy_off}</Offset>
      </CY>
      <CZ>
        <AxisType>{cz_type}</AxisType>
        <DataType>{z_code}</DataType>
        <Increment>{cz_inc}</Increment>
        <Offset>{cz_off}</Offset>
      </CZ>
    </Axes>
  </Record1>
  <Record2>
    <Date>{date}</Date>
    <Creator>{creator}</Creator>
    <Instrument>
      <Manufacturer>{man}</Manufacturer>
      <Model>{model}</Model>
      <Serial>{serial}</Serial>
      <Version>{version}</Version>
    </Instrument>
    <CalibrationDate>{caldate}</CalibrationDate>
    <ProbingSystem>
      <Type>{ptype}</Type>
      <Identification>{pident}</Identification>
    </ProbingSystem>
    <Comment>{comment}</Comment>
  </Record2>
  <Record3>
    <MatrixDimension>
      <SizeX>{nx}</SizeX>
      <SizeY>{ny}</SizeY>
      <SizeZ>1</SizeZ>
    </MatrixDimension>
    <DataLink>
      <PointDataLink>bindata/data.bin</PointDataLink>
      <MD5ChecksumPointData>{md5}</MD5ChecksumPointData>
    </DataLink>
  </Record3>
  <Record4>
    <ChecksumFile>md5checksum.hex</ChecksumFile>
  </Record4>
</p:ISO5436_2>
"#,
        revision = esc(revision),
        feature_type = esc(feature_type),
        cx_type = esc(&cx.axis_type),
        cx_dt = cx.data_type.code(),
        cx_inc = num(cx.increment),
        cx_off = num(cx.offset),
        cy_type = esc(&cy.axis_type),
        cy_dt = cy.data_type.code(),
        cy_inc = num(cy.increment),
        cy_off = num(cy.offset),
        cz_type = esc(&cz.axis_type),
        z_code = z_type.code(),
        cz_inc = num(cz.increment),
        cz_off = num(cz.offset),
        date = esc(&g.date),
        creator = esc(&g.creator),
        man = esc(&g.instrument.manufacturer),
        model = esc(&g.instrument.model),
        serial = esc(&g.instrument.serial),
        version = esc(&g.instrument.version),
        caldate = esc(&g.calibration_date),
        ptype = esc(&g.probing_system_type),
        pident = esc(&g.probing_system_identification),
        comment = esc(&g.comment),
        nx = nx,
        ny = ny,
        md5 = md5_point_data,
    )
}
