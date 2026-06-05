"""Crawl an NBTRD bullet study into a list of measurements.

NBTRD has no API and no bulk export, so the only programmatic path is to walk the
server-rendered pages — study → Firearm → Bullet → BulletMeasurement — collecting
the per-scan ``DownloadMeasurement`` GUIDs. Polite by default (throttle + retry +
browser UA). Firearm/bullet/land indices are assigned 1-based by page order and
encoded into ``Barrel{f}_Bullet{b}_Land{l}.x3p`` names so the ingest's LEA parser
and KM/KNM grouping work unchanged.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

BASE = "https://tsapps.nist.gov/NRBTD"
_UA = "verity-catalog/0.1 (+https://github.com/erichare/verity)"
_GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# Firearm anchors also carry the barrel's display label (e.g. "G1A9", "Brl03",
# "Unk"); capture it so questioned/unknown buckets can be skipped. Each firearm
# GUID appears twice on the study page (a label link + a "Bullet / CC" link),
# so dedupe by GUID keeping the first (the real label).
_FIREARM_ANCHOR_RE = re.compile(
    rf'/NRBTD/Studies/Firearm/Details/({_GUID})[^"]*"[^>]*>(.*?)</a>', re.S
)
_BULLET_RE = re.compile(rf"/NRBTD/Studies/Bullet/Details/({_GUID})")
_MEASUREMENT_RE = re.compile(rf"/NRBTD/Studies/BulletMeasurement/Details/({_GUID})")
# A firearm whose label is a questioned/unknown bucket groups bullets with no
# known source barrel. Those would seed false same-source (KM) pairs, so they are
# skipped by default. (Questioned bullets *nested under their true barrel* — the
# Hamby convention — are unaffected: this filters firearms, not bullets.)
_QUESTIONED_RE = re.compile(r"^(unk|unknown|quest|q\d)", re.I)


@dataclass
class CrawledScan:
    name: str  # "Barrel{f}_Bullet{b}_Land{l}.x3p"
    url: str  # DownloadMeasurement URL
    guid: str
    firearm_index: int
    bullet_index: int
    land_index: int


def _unique(items: list[str]) -> list[str]:
    """Order-preserving de-duplication."""
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _firearm_guids(study_html: str, *, skip_questioned: bool = True) -> list[str]:
    """Firearm GUIDs in document order, deduped by GUID (first label wins),
    with questioned/unknown buckets skipped when ``skip_questioned``."""
    seen: set[str] = set()
    out: list[str] = []
    for guid, label in _FIREARM_ANCHOR_RE.findall(study_html):
        if guid in seen:
            continue
        seen.add(guid)
        text = re.sub(r"<.*?>", "", label).strip()
        if skip_questioned and _QUESTIONED_RE.match(text):
            continue
        out.append(guid)
    return out


def _fetch(url: str, *, timeout: float = 60.0, retries: int = 4, delay: float = 0.6) -> str:
    import httpx

    last_error: Exception | None = None
    for attempt in range(retries):
        time.sleep(delay)
        try:
            resp = httpx.get(
                url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=timeout
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as err:
            last_error = err
            time.sleep(min(2.0**attempt, 10.0))
    raise RuntimeError(f"failed to fetch {url}") from last_error


def crawl_study(study_guid: str, *, fetch=None, skip_questioned: bool = True) -> list[CrawledScan]:
    """Enumerate every bullet measurement in a study, by page order. ``fetch`` is
    injectable (``fetch(url) -> html``) for testing without network. Questioned/
    unknown firearm buckets are skipped by default (no known source barrel)."""
    fetch = fetch or _fetch
    study_html = fetch(f"{BASE}/Studies/Studies/Details/{study_guid}")

    scans: list[CrawledScan] = []
    firearm_guids = _firearm_guids(study_html, skip_questioned=skip_questioned)
    for f_idx, firearm_guid in enumerate(firearm_guids, start=1):
        firearm_html = fetch(f"{BASE}/Studies/Firearm/Details/{firearm_guid}")
        for b_idx, bullet_guid in enumerate(_unique(_BULLET_RE.findall(firearm_html)), start=1):
            bullet_html = fetch(f"{BASE}/Studies/Bullet/Details/{bullet_guid}")
            for l_idx, meas_guid in enumerate(
                _unique(_MEASUREMENT_RE.findall(bullet_html)), start=1
            ):
                scans.append(
                    CrawledScan(
                        name=f"Barrel{f_idx}_Bullet{b_idx}_Land{l_idx}.x3p",
                        url=f"{BASE}/Studies/BulletMeasurement/DownloadMeasurement/{meas_guid}",
                        guid=meas_guid,
                        firearm_index=f_idx,
                        bullet_index=b_idx,
                        land_index=l_idx,
                    )
                )
    return scans


def crawl_to_manifest(
    study_guid: str,
    *,
    name: str,
    title: str | None = None,
    caliber: str | None = None,
    fetch=None,
    skip_questioned: bool = True,
) -> dict:
    """Crawl a study into a manifest dict (ready for ``Manifest.model_validate``)."""
    scans = crawl_study(study_guid, fetch=fetch, skip_questioned=skip_questioned)
    firearm_defaults = {"caliber": caliber} if caliber else {}
    return {
        "name": name,
        "title": title or name,
        "study": {
            "source": "nbtrd",
            "external_id": study_guid,
            "title": title or name,
            "nist_measurement": True,
        },
        "firearm_defaults": firearm_defaults,
        "source": {"kind": "url_list"},
        "files": [{"name": s.name, "url": s.url} for s in scans],
    }
