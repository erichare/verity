"""Offline virtual-kits ingest tests: real X3P bytes packed into synthetic zips
+ a synthetic inventory CSV (no network), exercising the multi-instrument path —
shared firearms across bullets & cartridge cases, instrument links, cartridge
region -> mark-type mapping, the bullet-strip single-land model, content-hash
dedup, resume, and the skip paths."""

import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, select

verity_x3p = pytest.importorskip("verity_x3p")
np = pytest.importorskip("numpy")

from verity_catalog import models  # noqa: E402
from verity_catalog.db import create_all  # noqa: E402
from verity_catalog.store import LocalBlobStore  # noqa: E402
from verity_catalog.virtual_kits import (  # noqa: E402
    ingest_virtual_kits,
    load_inventory,
    parse_name,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    create_all(engine)
    with Session(engine) as s:
        yield s


def _x3p_bytes(offset: float) -> bytes:
    """A small, valid, *distinct* X3P (distinct offset -> distinct content hash)."""
    arr = np.arange(12, dtype=float).reshape(3, 4) + offset
    surface = verity_x3p.Surface(arr, increment_x=1e-6, increment_y=1e-6)
    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        verity_x3p.write_x3p(surface, path)
        return Path(path).read_bytes()
    finally:
        Path(path).unlink()


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for arcname, data in members.items():
            zf.writestr(arcname, data)


def _write_inventory(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    """rows = (fname, kit, set, firearmID, same_source, Instrument) without header."""
    lines = ["fname,kit,set,firearmID,same_source,Instrument"]
    lines += [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Pure parsing                                                                #
# --------------------------------------------------------------------------- #
def test_parse_name_bullet_cartridge_regions_and_fixed():
    bu = parse_name("VBU1-S4-K1.x3p")
    assert bu and bu.entity == "bullet" and bu.item_id == "VBU1-S4-K1"
    assert bu.region is None and bu.enhanced is False

    enh = parse_name("VBU1-S4-Qu-Enh.x3p")
    assert enh and enh.enhanced is True and enh.item_id == "VBU1-S4-Qu"

    # the corrected re-scan groups with the same physical item + version
    fixed = parse_name("VBU3-S10-Qu_fixed.x3p")
    assert fixed and fixed.item_id == "VBU3-S10-Qu"
    enh_fixed = parse_name("VBU3-S10-Qu-Enh_fixed.x3p")
    assert enh_fixed and enh_fixed.item_id == "VBU3-S10-Qu" and enh_fixed.enhanced is True

    cc = parse_name("VCC1-S2-K1-BF.x3p")
    assert cc and cc.entity == "cartridge" and cc.region == "BF"
    assert parse_name("VCC1-S2-K1-FHS.x3p").region == "FHS"
    assert parse_name("VCC1-S1-K1.x3p").region is None  # region-less full scan

    assert parse_name("extra-file.x3p") is None  # not the convention


def test_load_inventory_normalises(tmp_path):
    csv_path = tmp_path / "inv.csv"
    _write_inventory(
        csv_path,
        [
            ("VBU1-S4-K1.x3p", "VBU1", "Set_04", "17", "TRUE", " CadreTM "),  # stray space
            ("VCC1-S1-K1.x3p", "VCC1", "Set_01", "31", "FALSE", "EvoFinder"),
        ],
    )
    inv = load_inventory(csv_path)
    assert inv["VBU1-S4-K1.x3p"].firearm_id == "17"
    assert inv["VBU1-S4-K1.x3p"].instrument == "CadreTM"  # stripped
    assert inv["VBU1-S4-K1.x3p"].same_source is True
    assert inv["VCC1-S1-K1.x3p"].same_source is False


def test_load_inventory_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="inventory"):
        load_inventory(tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# Full ingest                                                                 #
# --------------------------------------------------------------------------- #
def _fixture(tmp_path):
    """Build the synthetic dataset: two zips + an inventory CSV. Returns the
    three paths. Bullets and one cartridge case share firearm 17."""
    bu_members = {
        "Virtual_Kits_BU/VBU1/Set_04/VBU1-S4-K1.x3p": _x3p_bytes(0.0),
        "Virtual_Kits_BU/VBU1/Set_04/VBU1-S4-Qu.x3p": _x3p_bytes(1.0),
        "Virtual_Kits_BU/VBU1/Set_04/VBU1-S4-Qu-Enh.x3p": _x3p_bytes(2.0),  # same item
        "Virtual_Kits_BU/readme.txt": b"not an x3p",  # ignored (not .x3p)
    }
    cc_members = {
        "Virtual_Kits_CC/VCC1/Set_02/VCC1-S2-K1-BF.x3p": _x3p_bytes(3.0),
        "Virtual_Kits_CC/VCC1/Set_02/VCC1-S2-K1-FP.x3p": _x3p_bytes(4.0),
        "Virtual_Kits_CC/VCC1/Set_02/VCC1-S2-K1-EM.x3p": _x3p_bytes(5.0),
        "Virtual_Kits_CC/VCC1/Set_01/VCC1-S1-K1.x3p": _x3p_bytes(6.0),  # region-less
        "Virtual_Kits_CC/VCC1/Set_09/VCC1-S9-K2-BF.x3p": _x3p_bytes(7.0),  # no CSV row
        "Virtual_Kits_CC/extra-file.x3p": _x3p_bytes(8.0),  # unparsed name
    }
    bu_zip, cc_zip, inv = (
        tmp_path / "BU.zip",
        tmp_path / "CC.zip",
        tmp_path / "inv.csv",
    )
    _make_zip(bu_zip, bu_members)
    _make_zip(cc_zip, cc_members)
    _write_inventory(
        inv,
        [
            ("VBU1-S4-K1.x3p", "VBU1", "Set_04", "17", "TRUE", "EvoFinder"),
            ("VBU1-S4-Qu.x3p", "VBU1", "Set_04", "17", "TRUE", "CadreTM"),
            ("VBU1-S4-Qu-Enh.x3p", "VBU1", "Set_04", "17", "TRUE", "CadreTM"),
            ("VCC1-S2-K1-BF.x3p", "VCC1", "Set_02", "17", "TRUE", "Quantum"),
            ("VCC1-S2-K1-FP.x3p", "VCC1", "Set_02", "17", "TRUE", "Quantum"),
            ("VCC1-S2-K1-EM.x3p", "VCC1", "Set_02", "17", "TRUE", "Quantum"),
            ("VCC1-S1-K1.x3p", "VCC1", "Set_01", "31", "FALSE", "EvoFinder"),
            # VCC1-S9-K2-BF.x3p deliberately absent -> skipped_no_inventory
        ],
    )
    return bu_zip, cc_zip, inv


def test_ingest_builds_multi_instrument_hierarchy(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    bu_zip, cc_zip, inv = _fixture(tmp_path)

    stats = ingest_virtual_kits(session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip)

    assert stats == {
        "files": 9,  # 3 BU + 6 CC .x3p members (readme.txt excluded)
        "ingested": 7,
        "already_present": 0,
        "skipped_no_inventory": 1,  # VCC1-S9-K2-BF.x3p
        "skipped_unparsed": 1,  # extra-file.x3p
        "failed": 0,
    }

    # one shared study
    study = session.exec(select(models.Study)).one()
    assert study.source == "figshare"
    assert "Carriquiry" in study.creator

    # firearm 17 is shared across bullets AND cartridge cases
    firearms = {f.external_id: f for f in session.exec(select(models.Firearm)).all()}
    assert set(firearms) == {"Firearm17", "Firearm31"}
    f17 = firearms["Firearm17"]
    bullets_17 = session.exec(select(models.Bullet).where(models.Bullet.firearm_id == f17.id)).all()
    cases_17 = session.exec(
        select(models.CartridgeCase).where(models.CartridgeCase.firearm_id == f17.id)
    ).all()
    assert len(bullets_17) == 2  # VBU1-S4-K1, VBU1-S4-Qu
    assert len(cases_17) == 1  # VCC1-S2-K1

    # bullet "strips" -> one land each; the enhanced version is a 2nd scan on the
    # SAME land, not a new land
    lands = session.exec(select(models.Land)).all()
    assert len(lands) == 2 and all(ld.position == 1 for ld in lands)
    qu_bullet = next(b for b in bullets_17 if b.external_id == "VBU1-S4-Qu")
    qu_land = session.exec(select(models.Land).where(models.Land.bullet_id == qu_bullet.id)).one()
    qu_scans = session.exec(select(models.Scan).where(models.Scan.land_id == qu_land.id)).all()
    assert len(qu_scans) == 2  # raw + enhanced

    # cartridge regions -> distinct mark types under one case
    marks = session.exec(select(models.Mark)).all()
    assert {m.mark_type for m in marks} == {
        "breech_face",
        "firing_pin",
        "ejector",
        "full_headstamp",
    }

    # every ingested scan is linked to its instrument
    scans = session.exec(select(models.Scan)).all()
    assert len(scans) == 7
    assert all(s.instrument_id is not None for s in scans)
    instruments = {i.external_id: i for i in session.exec(select(models.Instrument)).all()}
    assert set(instruments) == {"EvoFinder", "Quantum", "CadreTM"}
    assert instruments["Quantum"].manufacturer == "LeadsOnline"
    bf = next(s for s in scans if s.filename == "VCC1-S2-K1-BF.x3p")
    assert bf.instrument.external_id == "Quantum"
    assert bf.mark.mark_type == "breech_face"
    assert bf.mark.cartridge_case.firearm.external_id == "Firearm17"


def test_ingest_resume_skips_without_reingest(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    bu_zip, cc_zip, inv = _fixture(tmp_path)

    first = ingest_virtual_kits(session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip)
    second = ingest_virtual_kits(session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip)

    assert first["ingested"] == 7
    assert second["ingested"] == 0 and second["already_present"] == 7
    # no duplicate rows on re-run
    assert len(session.exec(select(models.Scan)).all()) == 7
    assert len(session.exec(select(models.Firearm)).all()) == 2
    assert len(session.exec(select(models.Instrument)).all()) == 3


def test_ingest_dedups_identical_content(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    same = _x3p_bytes(0.0)
    bu_zip = tmp_path / "BU.zip"
    cc_zip = tmp_path / "CC.zip"
    inv = tmp_path / "inv.csv"
    _make_zip(
        bu_zip,
        {
            "VBU1-S1-K1.x3p": same,
            "VBU2-S1-K1.x3p": same,  # byte-identical -> dedups to one blob/scan
        },
    )
    _make_zip(cc_zip, {})  # empty (no cartridge members)
    _write_inventory(
        inv,
        [
            ("VBU1-S1-K1.x3p", "VBU1", "Set_01", "10", "TRUE", "EvoFinder"),
            ("VBU2-S1-K1.x3p", "VBU2", "Set_01", "11", "TRUE", "Quantum"),
        ],
    )

    stats = ingest_virtual_kits(session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip)

    assert stats["ingested"] == 2  # both members processed...
    assert store.count() == 1  # ...but identical content -> one blob
    assert len(session.exec(select(models.Scan)).all()) == 1
    # both bullets + their lands are still created (distinct items)
    assert len(session.exec(select(models.Bullet)).all()) == 2
    assert len(session.exec(select(models.Land)).all()) == 2


def test_ingest_limit_caps_members(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    bu_zip, cc_zip, inv = _fixture(tmp_path)

    stats = ingest_virtual_kits(
        session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip, limit=2
    )
    assert stats["files"] == 2


def _corrupt_fixture(tmp_path):
    """One good + one byte-corrupted bullet scan, both with inventory rows."""
    good = _x3p_bytes(0.0)
    bad = bytearray(_x3p_bytes(1.0))
    bad[len(bad) // 2] ^= 0xFF  # break the data -> zip CRC / X3P MD5 failure
    bu_zip, cc_zip, inv = tmp_path / "BU.zip", tmp_path / "CC.zip", tmp_path / "inv.csv"
    _make_zip(bu_zip, {"VBU1-S1-K1.x3p": good, "VBU1-S1-K2.x3p": bytes(bad)})
    _make_zip(cc_zip, {})
    _write_inventory(
        inv,
        [
            ("VBU1-S1-K1.x3p", "VBU1", "Set_01", "10", "TRUE", "EvoFinder"),
            ("VBU1-S1-K2.x3p", "VBU1", "Set_01", "10", "TRUE", "EvoFinder"),
        ],
    )
    return bu_zip, cc_zip, inv


def test_corrupt_scan_aborts_by_default(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    bu_zip, cc_zip, inv = _corrupt_fixture(tmp_path)
    with pytest.raises((ValueError, OSError)):
        ingest_virtual_kits(session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip)


def test_corrupt_scan_skipped_with_continue_on_error(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    bu_zip, cc_zip, inv = _corrupt_fixture(tmp_path)
    stats = ingest_virtual_kits(
        session, store, inventory_csv=inv, bu_zip=bu_zip, cc_zip=cc_zip, continue_on_error=True
    )
    assert stats["ingested"] == 1 and stats["failed"] == 1
    assert len(session.exec(select(models.Scan)).all()) == 1  # only the good scan lands


def test_ingest_missing_archive_raises(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    _, cc_zip, inv = _fixture(tmp_path)
    with pytest.raises(FileNotFoundError, match="archive"):
        ingest_virtual_kits(
            session, store, inventory_csv=inv, bu_zip=tmp_path / "nope.zip", cc_zip=cc_zip
        )
