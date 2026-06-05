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
