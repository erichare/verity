import pytest

pytest.importorskip("yaml")

from verity_catalog.harvest.base import UrlListSource  # noqa: E402
from verity_catalog.ingest import build_source, load_manifest  # noqa: E402


def test_load_sample_manifest():
    m = load_manifest("hamby252-barrel1-sample")
    assert m.name == "hamby252-barrel1-sample"
    assert m.study.source == "nbtrd"
    assert m.study.nist_measurement is True
    assert m.firearm_defaults.caliber == "9mm Luger"
    assert len(m.files) == 12
    assert all(f.url.startswith("https://tsapps.nist.gov/NRBTD/") for f in m.files)


def test_build_url_list_source():
    m = load_manifest("hamby252-barrel1-sample")
    src = build_source(m)
    assert isinstance(src, UrlListSource)
    assert len(src.discover()) == 12
