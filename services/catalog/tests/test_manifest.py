import pytest

pytest.importorskip("yaml")

from verity_catalog.harvest.base import UrlListSource  # noqa: E402
from verity_catalog.harvest.github import GithubSource  # noqa: E402
from verity_catalog.ingest import build_source, load_manifest  # noqa: E402


def test_load_sample_manifest():
    m = load_manifest("hamby252-barrel1-sample")
    assert m.name == "hamby252-barrel1-sample"
    assert m.entity == "bullet"  # default
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


def test_load_cartridge_manifest():
    m = load_manifest("fadul-cartridge-cases")
    assert m.name == "fadul-cartridge-cases"
    assert m.entity == "cartridge"
    assert m.mark_type == "breech_face"
    assert m.study.source == "csafe-isu"
    assert m.study.consecutively_manufactured is True
    assert m.study.creator == "CSAFE-ISU / Fadul et al."
    assert m.firearm_defaults.brand == "Glock"
    assert m.source.kind == "github"
    assert m.source.repo == "CSAFE-ISU/cartridgeCaseScans"
    assert m.source.path == "fadulMasked"


def test_build_github_source():
    m = load_manifest("fadul-cartridge-cases")
    src = build_source(m)
    assert isinstance(src, GithubSource)
    assert src.repo == "CSAFE-ISU/cartridgeCaseScans"
    assert src.ref == "main"
    assert src.path == "fadulMasked"


def test_cartridge_manifest_rejects_bad_mark_type():
    import pydantic

    from verity_catalog.ingest import Manifest

    with pytest.raises(pydantic.ValidationError, match="mark_type"):
        Manifest.model_validate(
            {
                "name": "bad",
                "entity": "cartridge",
                "mark_type": "not_a_mark",
                "study": {"source": "x", "external_id": "x"},
                "source": {"kind": "github", "repo": "o/r"},
            }
        )
