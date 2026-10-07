//! Packed validity conformance, including archive-link and checksum failures.

use std::io::{Cursor, Read, Write};
use verity_x3p::{read_x3p_bytes, write_x3p_to_bytes, ReadOptions, WriteOptions, X3pError};

const I16: &[u8] = include_bytes!("../../../tests/fixtures/validity-i.x3p");
const I32: &[u8] = include_bytes!("../../../tests/fixtures/validity-l.x3p");
const F32: &[u8] = include_bytes!("../../../tests/fixtures/validity-f.x3p");
const F64: &[u8] = include_bytes!("../../../tests/fixtures/validity-d.x3p");
const MASK: [bool; 10] = [
    true, false, true, false, true, false, false, true, true, false,
];

fn members(bytes: &[u8]) -> Vec<(String, Vec<u8>)> {
    let mut archive = zip::ZipArchive::new(Cursor::new(bytes)).unwrap();
    (0..archive.len())
        .map(|index| {
            let mut file = archive.by_index(index).unwrap();
            let name = file.name().to_owned();
            let mut data = Vec::new();
            file.read_to_end(&mut data).unwrap();
            (name, data)
        })
        .collect()
}

fn repack(files: Vec<(String, Vec<u8>)>) -> Vec<u8> {
    let mut archive = zip::ZipWriter::new(Cursor::new(Vec::new()));
    for (name, data) in files {
        archive
            .start_file(
                name,
                zip::write::SimpleFileOptions::default()
                    .compression_method(zip::CompressionMethod::Deflated),
            )
            .unwrap();
        archive.write_all(&data).unwrap();
    }
    archive.finish().unwrap().into_inner()
}

fn edit_xml(bytes: &[u8], edit: impl FnOnce(String) -> String) -> Vec<u8> {
    let mut files = members(bytes);
    let xml = files
        .iter_mut()
        .find(|(name, _)| name == "main.xml")
        .unwrap();
    xml.1 = edit(String::from_utf8(xml.1.clone()).unwrap()).into_bytes();
    repack(files)
}

fn remove_element(xml: String, tag: &str) -> String {
    let start = xml.find(&format!("<{tag}>")).unwrap();
    let end = xml.find(&format!("</{tag}>")).unwrap() + tag.len() + 3;
    format!("{}{}", &xml[..start], &xml[end..])
}

fn oversized_mask() -> Vec<u8> {
    let mut files = members(I16);
    files
        .iter_mut()
        .find(|(name, _)| name == "bindata/valid.bin")
        .unwrap()
        .1 = vec![0; 1024 * 1024];
    repack(files)
}

fn corrupt_mask_stream(bytes: &mut [u8]) {
    let offset = {
        let mut archive = zip::ZipArchive::new(Cursor::new(&*bytes)).unwrap();
        let file = archive.by_name("bindata/valid.bin").unwrap();
        file.data_start() as usize
    };
    // Deflate block type 3 is reserved. Attempting decompression must fail.
    bytes[offset] = 0x06;
}

#[test]
fn integer_masks_are_lsb_first_x_fastest_and_applied_after_z_scaling() {
    for (fixture, start) in [(I16, -10.0), (I32, 100000.0)] {
        let s = read_x3p_bytes(fixture, &ReadOptions::default()).unwrap();
        assert_eq!((s.nx(), s.ny()), (5, 2));
        for (i, (&height, &valid)) in s.data.iter().zip(s.mask.iter()).enumerate() {
            assert_eq!(valid, MASK[i], "point {i}");
            if valid {
                assert_eq!(height, (start + i as f64) * 0.5 + 100.0);
            } else {
                assert!(height.is_nan(), "masked point {i} must not retain a height");
            }
        }
    }
}

#[test]
fn float_masks_do_not_revive_nan_and_masked_values_roundtrip_as_nan() {
    for fixture in [F32, F64] {
        let s = read_x3p_bytes(fixture, &ReadOptions::default()).unwrap();
        for (i, (&height, &valid)) in s.data.iter().zip(s.mask.iter()).enumerate() {
            let expected = MASK[i] && i != 2;
            assert_eq!(valid, expected, "point {i}");
            assert_eq!(height.is_nan(), !expected);
            if expected {
                assert_eq!(height, i as f64);
            }
        }
        let bytes = write_x3p_to_bytes(&s, &WriteOptions::default()).unwrap();
        let back = read_x3p_bytes(&bytes, &ReadOptions::default()).unwrap();
        assert_eq!(back.mask, s.mask);
        assert!(back
            .data
            .iter()
            .zip(s.data.iter())
            .all(|(a, b)| a == b || (a.is_nan() && b.is_nan())));
    }
}

#[test]
fn declared_missing_mask_is_rejected() {
    let files = members(I16)
        .into_iter()
        .filter(|(n, _)| n != "bindata/valid.bin")
        .collect();
    let err = read_x3p_bytes(&repack(files), &ReadOptions::default()).unwrap_err();
    assert!(err.to_string().contains("valid.bin"), "{err}");
}

#[test]
fn mask_length_is_exact_even_when_checksum_verification_is_disabled() {
    for length in [0, 1, 3, 10] {
        let mut files = members(I16);
        files
            .iter_mut()
            .find(|(n, _)| n == "bindata/valid.bin")
            .unwrap()
            .1 = vec![255; length];
        let opts = ReadOptions {
            verify_checksums: false,
        };
        let err = read_x3p_bytes(&repack(files), &opts).unwrap_err();
        assert!(err.to_string().contains("validity mask length"), "{err}");
    }
}

#[test]
fn oversized_declared_mask_is_rejected_before_decompression() {
    let mut bytes = oversized_mask();
    corrupt_mask_stream(&mut bytes);
    let err = read_x3p_bytes(&bytes, &ReadOptions::default()).unwrap_err();
    assert!(
        matches!(&err, X3pError::Malformed(message) if message.contains("validity mask length is 1048576 bytes, expected 2")),
        "{err}"
    );
}

#[test]
fn forged_mask_size_cannot_allow_unbounded_decompression() {
    let mut bytes = oversized_mask();
    let name = b"bindata/valid.bin";
    let central = (0..bytes.len() - 46)
        .find(|&offset| {
            bytes[offset..offset + 4] == *b"PK\x01\x02"
                && usize::from(u16::from_le_bytes(
                    bytes[offset + 28..offset + 30].try_into().unwrap(),
                )) == name.len()
                && bytes.get(offset + 46..offset + 46 + name.len()) == Some(name.as_slice())
        })
        .unwrap();
    // Lie about the uncompressed size in the central directory. The actual
    // Deflate stream still contains 1 MiB, so checking this field is not enough.
    bytes[central + 24..central + 28].copy_from_slice(&2_u32.to_le_bytes());
    let mut archive = zip::ZipArchive::new(Cursor::new(&bytes)).unwrap();
    assert_eq!(archive.by_name("bindata/valid.bin").unwrap().size(), 2);
    let err = read_x3p_bytes(
        &bytes,
        &ReadOptions {
            verify_checksums: false,
        },
    )
    .unwrap_err();
    assert!(
        matches!(&err, X3pError::Malformed(message) if message.contains("validity mask length is 3 bytes, expected 2")),
        "must stop after the first unexpected byte: {err}"
    );
}

#[test]
fn short_point_data_is_rejected_before_reading_mask() {
    let mut bytes = edit_xml(&oversized_mask(), |xml| {
        xml.replace("<SizeX>5</SizeX>", "<SizeX>4194304</SizeX>")
    });
    // Dimensions now declare exactly 1 MiB of validity, but the point stream
    // still holds only 10 values. Reject that contradiction before the mask.
    corrupt_mask_stream(&mut bytes);
    let err = read_x3p_bytes(&bytes, &ReadOptions::default()).unwrap_err();
    assert!(
        matches!(&err, X3pError::Malformed(message) if message.contains("data.bin too short")),
        "{err}"
    );
}

#[test]
fn mask_checksum_detects_corruption_and_has_an_explicit_recovery_opt_out() {
    let mut files = members(I16);
    files
        .iter_mut()
        .find(|(n, _)| n == "bindata/valid.bin")
        .unwrap()
        .1[0] ^= 1;
    let bytes = repack(files);
    assert!(matches!(
        read_x3p_bytes(&bytes, &ReadOptions::default()),
        Err(X3pError::Checksum { .. })
    ));
    let recovered = read_x3p_bytes(
        &bytes,
        &ReadOptions {
            verify_checksums: false,
        },
    )
    .unwrap();
    assert!(!recovered.mask[[0, 0]]);
    assert!(recovered.data[[0, 0]].is_nan());
}

#[test]
fn incomplete_or_malformed_validity_declarations_are_rejected() {
    for tag in ["ValidPointsLink", "MD5ChecksumValidPoints"] {
        let bytes = edit_xml(I16, |xml| remove_element(xml, tag));
        assert!(
            read_x3p_bytes(&bytes, &ReadOptions::default()).is_err(),
            "missing {tag}"
        );
    }
    for invalid in ["", "not-a-checksum", "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"] {
        let bytes = edit_xml(I16, |xml| {
            let start =
                xml.find("<MD5ChecksumValidPoints>").unwrap() + "<MD5ChecksumValidPoints>".len();
            let end = xml.find("</MD5ChecksumValidPoints>").unwrap();
            format!("{}{invalid}{}", &xml[..start], &xml[end..])
        });
        assert!(read_x3p_bytes(
            &bytes,
            &ReadOptions {
                verify_checksums: false
            }
        )
        .is_err());
    }
}

#[test]
fn custom_links_resolve_relative_to_the_unique_main_xml() {
    let bytes = edit_xml(I16, |xml| {
        xml.replace("bindata/data.bin", "height/raw.bin")
            .replace("bindata/valid.bin", "quality/selected.bin")
    });
    let files = members(&bytes)
        .into_iter()
        .map(|(name, data)| {
            let name = name
                .replace("bindata/data.bin", "height/raw.bin")
                .replace("bindata/valid.bin", "quality/selected.bin");
            (format!("wrapped/{name}"), data)
        })
        .collect();
    let s = read_x3p_bytes(&repack(files), &ReadOptions::default()).unwrap();
    assert_eq!(s.mask.iter().copied().collect::<Vec<_>>(), MASK);
}

#[test]
fn dot_components_resolve_in_both_links_and_member_names() {
    let bytes = edit_xml(I16, |xml| xml.replace("bindata/", "./bindata/./"));
    for prefix in ["", "./", "./wrapped/./"] {
        let files = members(&bytes)
            .into_iter()
            .map(|(name, data)| {
                let name = name.replace("bindata/", "./bindata/./");
                (format!("{prefix}{name}"), data)
            })
            .collect();
        let s = read_x3p_bytes(&repack(files), &ReadOptions::default()).unwrap();
        assert_eq!(s.mask.iter().copied().collect::<Vec<_>>(), MASK);
    }
}

#[test]
fn ambiguous_normalized_member_names_are_rejected() {
    for duplicate in ["bindata/data.bin", "bindata/valid.bin"] {
        let mut files = members(I16);
        let (_, data) = files.iter().find(|(name, _)| name == duplicate).unwrap();
        files.push((format!("./{duplicate}"), data.clone()));
        let err = read_x3p_bytes(&repack(files), &ReadOptions::default()).unwrap_err();
        assert!(
            matches!(&err, X3pError::Malformed(message) if message.contains("ambiguous linked archive member")),
            "{err}"
        );
    }
}

#[test]
fn nonlocal_and_escaping_validity_links_are_rejected() {
    for link in [
        "",
        "../valid.bin",
        "/valid.bin",
        "https://example.com/valid.bin",
        "file:///tmp/valid.bin",
        "C:\\valid.bin",
        "quality/../../valid.bin",
    ] {
        let bytes = edit_xml(I16, |xml| xml.replace("bindata/valid.bin", link));
        assert!(
            read_x3p_bytes(&bytes, &ReadOptions::default()).is_err(),
            "{link}"
        );
    }
}

#[test]
fn undeclared_mask_does_not_override_nan_fallback() {
    let bytes = edit_xml(F64, |xml| {
        remove_element(
            remove_element(xml, "ValidPointsLink"),
            "MD5ChecksumValidPoints",
        )
    });
    let s = read_x3p_bytes(&bytes, &ReadOptions::default()).unwrap();
    for (i, &valid) in s.mask.iter().enumerate() {
        assert_eq!(valid, i != 2);
    }
}
