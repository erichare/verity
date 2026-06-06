import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine

from verity_catalog import models
from verity_catalog.db import create_all


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    create_all(engine)
    with Session(engine) as s:
        yield s


def _bullet_scan(session, firearm, *, content_hash, position=1):
    bullet = models.Bullet(firearm_id=firearm.id)
    session.add(bullet)
    session.commit()
    session.refresh(bullet)
    land = models.Land(bullet_id=bullet.id, position=position)
    session.add(land)
    session.commit()
    session.refresh(land)
    scan = models.Scan(
        land_id=land.id,
        modality="x3p_3d",
        content_hash=content_hash,
        size_bytes=100,
        source="figshare",
        source_ref="10.x/hamby44",
        lateral_resolution_x=0.645,
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def test_full_hierarchy_navigates(session):
    study = models.Study(source="figshare", external_id="10.x/hamby44", title="Hamby 44")
    session.add(study)
    session.commit()
    session.refresh(study)
    firearm = models.Firearm(
        study_id=study.id,
        brand="Ruger",
        model="P-85",
        caliber="9mm Luger",
        n_lands=6,
        twist="right",
    )
    session.add(firearm)
    session.commit()
    session.refresh(firearm)

    scan = _bullet_scan(session, firearm, content_hash="a" * 64)

    # Navigate scan -> land -> bullet -> firearm -> study and back.
    assert scan.land.bullet.firearm.study.title == "Hamby 44"
    assert study.firearms[0].bullets[0].lands[0].scans[0].content_hash == "a" * 64


def test_same_source_vs_different_source_is_derivable(session):
    study = models.Study(source="nbtrd", external_id="guid-1", title="S")
    session.add(study)
    session.commit()
    session.refresh(study)
    f1 = models.Firearm(study_id=study.id, brand="Ruger")
    f2 = models.Firearm(study_id=study.id, brand="Ruger")
    session.add(f1)
    session.add(f2)
    session.commit()
    session.refresh(f1)
    session.refresh(f2)

    a = _bullet_scan(session, f1, content_hash="1" * 64)
    b = _bullet_scan(session, f1, content_hash="2" * 64)
    c = _bullet_scan(session, f2, content_hash="3" * 64)

    src = lambda scan: scan.land.bullet.firearm_id  # noqa: E731
    assert src(a) == src(b)  # known-match (same firearm)
    assert src(a) != src(c)  # known-non-match (different firearm)


def test_cartridge_case_path(session):
    study = models.Study(source="nbtrd", external_id="guid-2", title="CC")
    session.add(study)
    session.commit()
    session.refresh(study)
    firearm = models.Firearm(study_id=study.id, brand="Glock", firing_pin_class="Glock-type")
    session.add(firearm)
    session.commit()
    session.refresh(firearm)
    cc = models.CartridgeCase(firearm_id=firearm.id, label="CC1")
    session.add(cc)
    session.commit()
    session.refresh(cc)
    mark = models.Mark(cartridge_case_id=cc.id, mark_type="breech_face")
    session.add(mark)
    session.commit()
    session.refresh(mark)
    scan = models.Scan(
        mark_id=mark.id,
        modality="x3p_3d",
        content_hash="f" * 64,
        size_bytes=1,
        source="nbtrd",
        source_ref="guid-2",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    assert scan.mark.cartridge_case.firearm.firing_pin_class == "Glock-type"
    assert scan.land is None


def test_study_source_external_id_unique(session):
    session.add(models.Study(source="figshare", external_id="dup", title="A"))
    session.commit()
    session.add(models.Study(source="figshare", external_id="dup", title="B"))
    with pytest.raises(IntegrityError):
        session.commit()


def _study_firearm(session, external_id="g-trace"):
    study = models.Study(source="nbtrd", external_id=external_id, title="T")
    session.add(study)
    session.commit()
    session.refresh(study)
    firearm = models.Firearm(study_id=study.id, brand="Ruger")
    session.add(firearm)
    session.commit()
    session.refresh(firearm)
    return study, firearm


def test_scan_trace_round_trip(session):
    _, firearm = _study_firearm(session)
    scan = _bullet_scan(session, firearm, content_hash="a" * 64)
    tr = models.ScanTrace(
        scan_id=scan.id,
        pipeline_version="stage0-v1",
        content_hash_scan=scan.content_hash,
        lambda_s=4e-6,
        lambda_c=250e-6,
        striae_angle_deg=178.5,
        tilt_deg=-88.5,
        crop_lo=10,
        crop_hi=200,
        n_signature=190,
        png_hash="p" * 64,
        npz_hash="n" * 64,
    )
    session.add(tr)
    session.commit()

    session.refresh(scan)
    assert scan.traces[0].pipeline_version == "stage0-v1"
    assert scan.traces[0].scan.content_hash == "a" * 64  # relationship navigates both ways
    assert scan.traces[0].crop_hi - scan.traces[0].crop_lo == 190


def test_scan_trace_unique_per_pipeline_version(session):
    _, firearm = _study_firearm(session, external_id="g-uniq")
    scan = _bullet_scan(session, firearm, content_hash="b" * 64)
    for _ in range(2):
        session.add(
            models.ScanTrace(
                scan_id=scan.id, pipeline_version="stage0-v1", content_hash_scan=scan.content_hash
            )
        )
    with pytest.raises(IntegrityError):
        session.commit()


def test_pair_diagnostic_round_trip(session):
    study, firearm = _study_firearm(session, external_id="g-pair")
    b1 = models.Bullet(firearm_id=firearm.id)
    b2 = models.Bullet(firearm_id=firearm.id)
    session.add(b1)
    session.add(b2)
    session.commit()
    session.refresh(b1)
    session.refresh(b2)

    pd = models.PairDiagnostic(
        study_id=study.id,
        bullet_a_id=b1.id,
        bullet_b_id=b2.id,
        pipeline_version="stage0-v1",
        label=1,
        offset=2,
        diag_mean=0.7,
        diag_min=0.5,
        diag_contrast=0.4,
        offset_margin=0.2,
        lag_coherence=0.9,
        png_hash="p" * 64,
    )
    session.add(pd)
    session.commit()

    got = session.get(models.PairDiagnostic, pd.id)
    assert got.label == 1
    assert got.offset == 2
    assert got.diag_contrast == 0.4
