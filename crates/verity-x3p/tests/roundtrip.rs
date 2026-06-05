//! Round-trip and real-fixture conformance tests for the X3P codec.

use ndarray::{array, Array2};
use verity_x3p::{
    read_x3p, read_x3p_bytes, write_x3p, write_x3p_to_bytes, DataType, ReadOptions, Surface,
    WriteOptions,
};

/// Compare two height matrices treating NaN as equal to NaN.
fn data_eq(a: &Array2<f64>, b: &Array2<f64>) -> bool {
    if a.dim() != b.dim() {
        return false;
    }
    a.iter()
        .zip(b.iter())
        .all(|(x, y)| (x.is_nan() && y.is_nan()) || x == y)
}

fn sample_surface() -> Surface {
    // Deliberately non-square (ny=3, nx=5) to catch any X/Y transposition,
    // with one invalid (NaN) point.
    let data = array![
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [10.0, 11.0, f64::NAN, 13.0, 14.0],
        [20.0, 21.0, 22.0, 23.0, 24.0],
    ];
    let mut s = Surface::from_data(data);
    s.cx.increment = 1.5625;
    s.cx.offset = 0.5;
    s.cy.increment = 2.0;
    s.general.creator = "Verity Test".to_string();
    // Comment exercises XML escaping on the write path.
    s.general.comment = r#"round-trip & <escaping> "quotes" 'apostrophe'"#.to_string();
    s.general.instrument.manufacturer = "Acme Metrology".to_string();
    s
}

#[test]
fn synthetic_roundtrip_f64() {
    let s = sample_surface();
    let bytes = write_x3p_to_bytes(&s, &WriteOptions::default()).expect("write");
    let back = read_x3p_bytes(&bytes, &ReadOptions::default()).expect("read");

    assert_eq!((back.ny(), back.nx()), (3, 5));
    assert_eq!(back.cz.data_type, DataType::F64);
    assert_eq!(back.cx.increment, 1.5625);
    assert_eq!(back.cx.offset, 0.5);
    assert_eq!(back.cy.increment, 2.0);
    assert!(data_eq(&back.data, &s.data), "heights must round-trip");
    assert_eq!(back.mask, s.mask, "validity mask must round-trip");
    assert!(!back.mask[[1, 2]], "the NaN point stays invalid");
    assert_eq!(back.general.creator, "Verity Test");
    assert_eq!(
        back.general.comment, s.general.comment,
        "XML escaping must decode"
    );
    assert_eq!(back.general.instrument.manufacturer, "Acme Metrology");
    assert_eq!(back.feature_type, "SUR");
}

#[test]
fn synthetic_roundtrip_f32() {
    let s = sample_surface();
    let opts = WriteOptions {
        z_type: DataType::F32,
    };
    let bytes = write_x3p_to_bytes(&s, &opts).expect("write");
    let back = read_x3p_bytes(&bytes, &ReadOptions::default()).expect("read");

    assert_eq!(back.cz.data_type, DataType::F32);
    // f32 is exact for these small integers and 1.5625, so equality holds.
    assert!(data_eq(&back.data, &s.data));
    assert_eq!(back.mask, s.mask);
}

#[test]
fn roundtrip_via_file() {
    let s = sample_surface();
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("scan.x3p");
    write_x3p(&s, &path, &WriteOptions::default()).expect("write file");
    let back = read_x3p(&path).expect("read file");
    assert!(data_eq(&back.data, &s.data));
    assert_eq!(back.mask, s.mask);
}

#[test]
fn bad_checksum_is_rejected() {
    let s = sample_surface();
    let mut bytes = write_x3p_to_bytes(&s, &WriteOptions::default()).expect("write");
    // Corrupt a byte well inside the deflated data; the stored MD5 will no
    // longer match, so a verifying read must fail.
    let n = bytes.len();
    bytes[n / 2] ^= 0xFF;
    let res = read_x3p_bytes(&bytes, &ReadOptions::default());
    assert!(res.is_err(), "corrupted archive must not read as valid");
}

#[test]
fn real_csafe_logo_conformance() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/fixtures/csafe-logo.x3p"
    );

    // Reads with checksum verification ON — proves our MD5 matches the file's.
    let s = read_x3p(path).expect("read real csafe-logo.x3p with checksum verification");

    eprintln!(
        "csafe-logo: nx={} ny={} z_type={:?} inc=({}, {}) creator={:?} valid_pts={}",
        s.nx(),
        s.ny(),
        s.cz.data_type,
        s.increment_x(),
        s.increment_y(),
        s.general.creator,
        s.mask.iter().filter(|&&m| m).count(),
    );

    // 741 x 419 = 310,479 points; data.bin is 2,483,832 bytes = 310,479 * 8,
    // so the logo is stored as float64 (D). Increments are in SI metres (~0.645 um).
    assert_eq!((s.nx(), s.ny()), (741, 419));
    assert_eq!(s.cz.data_type, DataType::F64);
    assert_eq!(s.nx() * s.ny(), 310_479);
    assert!(s.mask.iter().any(|&m| m), "must contain valid points");

    // Round-trip the real file in its own dtype (D -> D is exact).
    let bytes = write_x3p_to_bytes(
        &s,
        &WriteOptions {
            z_type: s.cz.data_type,
        },
    )
    .expect("write logo");
    let back = read_x3p_bytes(&bytes, &ReadOptions::default()).expect("re-read logo");
    assert_eq!(back.data.dim(), s.data.dim());
    assert_eq!(back.mask, s.mask);
    assert!(
        data_eq(&back.data, &s.data),
        "real-file heights must round-trip"
    );
    assert_eq!(
        back.increment_x(),
        s.increment_x(),
        "X increment must round-trip exactly"
    );
    assert_eq!(
        back.increment_y(),
        s.increment_y(),
        "Y increment must round-trip exactly"
    );
}
