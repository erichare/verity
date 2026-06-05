from verity_catalog.harvest.nbtrd import crawl_study, crawl_to_manifest
from verity_catalog.ingest import Manifest, parse_lea


def _guid(n: int) -> str:
    return f"{n:08d}-0000-0000-0000-000000000000"


def _fake_site():
    """A 2-firearm × 2-bullet × 3-measurement study, served from memory."""
    firearms = [_guid(1), _guid(2)]
    bullets = {firearms[0]: [_guid(11), _guid(12)], firearms[1]: [_guid(21), _guid(22)]}
    measurements, counter = {}, 100
    for f in firearms:
        for b in bullets[f]:
            measurements[b] = [_guid(counter + i) for i in range(3)]
            counter += 3

    def fetch(url: str) -> str:
        if "/Studies/Studies/Details/" in url:
            return "".join(
                f'<a href="/NRBTD/Studies/Firearm/Details/{f}">Bullet / CC</a>' for f in firearms
            )
        for f in firearms:
            if f"/Firearm/Details/{f}" in url:
                return "".join(
                    f'<a href="/NRBTD/Studies/Bullet/Details/{b}">Measurements</a>'
                    for b in bullets[f]
                )
        for b, ms in measurements.items():
            if f"/Bullet/Details/{b}" in url:
                return "".join(
                    f'<a href="/NRBTD/Studies/BulletMeasurement/Details/{m}">scan.x3p</a>'
                    for m in ms
                )
        return ""

    return fetch


def test_crawl_study_enumerates_hierarchy():
    scans = crawl_study(_guid(999), fetch=_fake_site())
    assert len(scans) == 2 * 2 * 3
    assert scans[0].name == "Barrel1_Bullet1_Land1.x3p"
    assert scans[-1].name == "Barrel2_Bullet2_Land3.x3p"
    assert len({s.guid for s in scans}) == 12  # unique
    assert parse_lea(scans[5].name) is not None  # ingest can parse the names


def test_crawl_to_manifest_is_valid():
    manifest_dict = crawl_to_manifest(
        _guid(999), name="test-study", caliber="9mm Luger", fetch=_fake_site()
    )
    manifest = Manifest.model_validate(manifest_dict)
    assert manifest.name == "test-study"
    assert manifest.study.source == "nbtrd"
    assert manifest.study.external_id == _guid(999)
    assert manifest.firearm_defaults.caliber == "9mm Luger"
    assert len(manifest.files) == 12
    assert all("DownloadMeasurement/" in f.url for f in manifest.files)
