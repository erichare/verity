"""Ingest the CSAFE/ISU **virtual-kits** dataset — the catalog's first
*multi-instrument* set: the same bullets and cartridge cases imaged on three 3D
systems (Leeds **Evofinder**, LeadsOnline **Quantum**, Cadre **TopMatch**).

Source: figshare article ``30854414`` (Hofmann, Carriquiry, et al.; Iowa State),
**CC BY 4.0**, directly downloadable. DOI ``10.25380/iastate.30854414.v1``.

Unlike the manifest-driven sources, the scans here live inside two large zips
(``Virtual_Kits_BU.zip`` ~9.7 GB bullets, ``Virtual_Kits_CC.zip`` ~8.5 GB
cartridge cases) and their provenance lives in a companion
``virtual-kits-inventory.csv`` rather than in the filenames. So this module:

1. streams the figshare files into a local cache (never into RAM),
2. iterates the ``.x3p`` members of each zip,
3. joins each member to its inventory row for the true source firearm and the
   scanning instrument, and
4. builds ``Study → Firearm → {Bullet → Land | CartridgeCase → Mark} → Scan``,
   keying the firearm by its dataset-wide ``firearmID`` so a firearm's bullets
   *and* cartridge cases hang off one shared :class:`~.models.Firearm`.

The bullet files are whole *strips* (the land-engraved areas stitched into one
surface), so each is modelled as a bullet with a single land. Cartridge-case
files may be split by region (breech face, full headstamp, firing pin, ejector);
each region becomes its own :class:`~.models.Mark`.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from . import ingest, models
from .harvest.base import USER_AGENT
from .store import BlobStore

# --------------------------------------------------------------------------- #
# Dataset constants                                                           #
# --------------------------------------------------------------------------- #
FIGSHARE_API = "https://api.figshare.com/v2"
ARTICLE_ID = 30854414
DOI_URL = "https://doi.org/10.25380/iastate.30854414.v1"

STUDY_SOURCE = "figshare"
STUDY_EXTERNAL_ID = "iastate-virtual-kits-30854414"

CACHE_DIR = Path.home() / ".cache" / "verity" / "virtual-kits"
INVENTORY_CSV = "virtual-kits-inventory.csv"
BU_ZIP = "Virtual_Kits_BU.zip"
CC_ZIP = "Virtual_Kits_CC.zip"

# Inventory ``Instrument`` value -> (manufacturer, model). The same physical
# items were imaged on all three; the per-scan instrument comes from the CSV,
# never the filename.
INSTRUMENTS: dict[str, tuple[str, str]] = {
    "EvoFinder": ("Leeds Precision Instruments", "Evofinder"),
    "Quantum": ("LeadsOnline", "Quantum"),
    "CadreTM": ("Cadre Research Labs", "TopMatch"),
}
INSTRUMENT_KIND = "3D optical surface scanner"

# Cartridge-case region suffix -> mark type. A region-less (or ``FHS``) scan is
# the all-in-one "full headstamp" capture that incorporates breech face, primer,
# ejector and firing pin in a single surface.
REGION_TO_MARK: dict[str, str] = {
    "BF": "breech_face",
    "FHS": "full_headstamp",
    "FP": "firing_pin",
    "EM": "ejector",
}
DEFAULT_MARK_TYPE = "full_headstamp"

_ITEM_RE = re.compile(r"^(K\d+|Qu)$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Filename + inventory parsing                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ParsedName:
    """Structure decoded from a ``VBUX-SY-GG[-region][-Enh].x3p`` filename."""

    kit: str  # e.g. "VBU1" / "VCC1"
    set_id: str  # e.g. "S4"
    item: str  # e.g. "K1" / "Qu"  (``_fixed`` re-scan suffix normalised away)
    region: str | None  # cartridge region (BF/FHS/FP/EM) or None
    enhanced: bool  # an -Enh enhanced rendering of the same physical item

    @property
    def entity(self) -> str:
        return "bullet" if self.kit.upper().startswith("VBU") else "cartridge"

    @property
    def item_id(self) -> str:
        """Stable identity of the *physical* item — regions/enhanced versions of
        one item share it (e.g. ``VBU1-S4-Qu``)."""
        return f"{self.kit}-{self.set_id}-{self.item}"


def parse_name(fname: str) -> ParsedName | None:
    """Decode a scan filename, or ``None`` if it doesn't match the convention.

    ``_fixed`` (a corrected re-scan) is treated as the same item/version, so
    ``VBU3-S10-Qu_fixed.x3p`` groups with ``VBU3-S10-Qu``.
    """
    stem = Path(fname).name
    if stem.lower().endswith(".x3p"):
        stem = stem[:-4]
    tokens = stem.split("-")
    if len(tokens) < 3:
        return None
    kit, set_id = tokens[0], tokens[1]
    item = tokens[2].replace("_fixed", "")
    if not _ITEM_RE.match(item):
        return None
    region: str | None = None
    enhanced = False
    for tok in tokens[3:]:
        base = tok.replace("_fixed", "")
        if base.upper() in REGION_TO_MARK:
            region = base.upper()
        elif base.lower() == "enh":
            enhanced = True
    return ParsedName(kit=kit, set_id=set_id, item=item, region=region, enhanced=enhanced)


@dataclass(frozen=True)
class InventoryRow:
    firearm_id: str
    instrument: str
    kit: str
    set_id: str
    same_source: bool | None


def load_inventory(csv_path: Path) -> dict[str, InventoryRow]:
    """Read the inventory into ``{filename: InventoryRow}``.

    The CSV (``fname,kit,set,firearmID,same_source,Instrument``) is the dataset's
    complete ground-truth index — the join key from each zip member to its true
    source firearm and scanning instrument.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"virtual-kits inventory not found at {csv_path}. Download the dataset "
            f"first (figshare article {ARTICLE_ID}); see `download_dataset`."
        )
    rows: dict[str, InventoryRow] = {}
    with csv_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            fname = (row.get("fname") or "").strip()
            if not fname:
                continue
            same = (row.get("same_source") or "").strip().upper()
            rows[fname] = InventoryRow(
                firearm_id=(row.get("firearmID") or "").strip(),
                instrument=(row.get("Instrument") or "").strip(),
                kit=(row.get("kit") or "").strip(),
                set_id=(row.get("set") or "").strip(),
                same_source={"TRUE": True, "FALSE": False}.get(same),
            )
    return rows


# --------------------------------------------------------------------------- #
# Idempotent upserts specific to this dataset                                 #
# --------------------------------------------------------------------------- #
def get_or_create_study(session: Session) -> models.Study:
    study = session.exec(
        select(models.Study).where(
            models.Study.source == STUDY_SOURCE,
            models.Study.external_id == STUDY_EXTERNAL_ID,
        )
    ).first()
    if study:
        return study
    study = models.Study(
        source=STUDY_SOURCE,
        external_id=STUDY_EXTERNAL_ID,
        title="Virtual kits — bullets & cartridge cases on Cadre, Quantum, Evofinder",
        creator="H. Hofmann, A. Carriquiry, et al. (Iowa State / CSAFE; Houston FSC)",
        references=DOI_URL,
        persistence=False,
        consecutively_manufactured=False,
        nist_measurement=False,
    )
    session.add(study)
    session.commit()
    session.refresh(study)
    return study


def get_or_create_instrument(
    session: Session, cache: dict[str, models.Instrument], name: str
) -> models.Instrument | None:
    """Resolve an inventory instrument label to a catalog :class:`Instrument`,
    creating it once. Unknown labels yield ``None`` (the scan is still ingested,
    just without an instrument link)."""
    if not name:
        return None
    if name in cache:
        return cache[name]
    existing = session.exec(
        select(models.Instrument).where(models.Instrument.external_id == name)
    ).first()
    if existing is None:
        manufacturer, model = INSTRUMENTS.get(name, (None, None))
        existing = models.Instrument(
            external_id=name, manufacturer=manufacturer, model=model, kind=INSTRUMENT_KIND
        )
        session.add(existing)
        session.commit()
        session.refresh(existing)
    cache[name] = existing
    return existing


# --------------------------------------------------------------------------- #
# Ingest                                                                      #
# --------------------------------------------------------------------------- #
def _catalog_one(
    session: Session,
    store: BlobStore,
    study: models.Study,
    instruments: dict[str, models.Instrument],
    parsed: ParsedName,
    row: InventoryRow,
    data: bytes,
    *,
    fname: str,
    source_ref: str,
) -> None:
    """Build the containment path for one scan and persist it."""
    firearm = ingest.get_or_create_firearm(
        session, study, f"Firearm{row.firearm_id}", ingest.FirearmDefaults()
    )
    instrument = get_or_create_instrument(session, instruments, row.instrument)
    if parsed.entity == "bullet":
        # A bullet "strip" is the whole land-engraved surface stitched into one
        # file -> model it as a bullet with a single land.
        bullet = ingest.get_or_create_bullet(session, firearm, parsed.item_id)
        land = ingest.get_or_create_land(session, bullet, 1, parsed.item_id)
        ingest.ingest_scan(
            session,
            store,
            data,
            name=fname,
            source=STUDY_SOURCE,
            source_ref=source_ref,
            land=land,
            instrument=instrument,
        )
    else:
        case = ingest.get_or_create_cartridge_case(
            session, firearm, parsed.item_id, label=parsed.item_id
        )
        mark_type = REGION_TO_MARK.get(parsed.region or "", DEFAULT_MARK_TYPE)
        mark = ingest.get_or_create_mark(session, case, f"{parsed.item_id}-{mark_type}", mark_type)
        ingest.ingest_scan(
            session,
            store,
            data,
            name=fname,
            source=STUDY_SOURCE,
            source_ref=source_ref,
            mark=mark,
            instrument=instrument,
        )


def ingest_virtual_kits(
    session: Session,
    store: BlobStore,
    *,
    cache_dir: Path = CACHE_DIR,
    inventory_csv: Path | None = None,
    bu_zip: Path | None = None,
    cc_zip: Path | None = None,
    limit: int | None = None,
    continue_on_error: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Ingest the cached virtual-kits zips into the catalog.

    Idempotent and **resumable**: a scan already cataloged (matched by its
    ``source_ref``) is skipped *without* re-reading its bytes, so an interrupted
    pull can simply be re-run.

    With ``continue_on_error`` a scan that fails validation (a malformed X3P or a
    bad zip member) is counted in ``stats["failed"]`` and the pull continues,
    rather than aborting the whole run — useful for a large dataset where one bad
    file shouldn't sink the other ~hundreds. The default stays strict (raise).
    """
    inventory = load_inventory(inventory_csv or cache_dir / INVENTORY_CSV)
    study = get_or_create_study(session)
    instruments: dict[str, models.Instrument] = {}
    stats = {
        "files": 0,
        "ingested": 0,
        "already_present": 0,
        "skipped_no_inventory": 0,
        "skipped_unparsed": 0,
        "failed": 0,
    }

    archives = [
        (bu_zip or cache_dir / BU_ZIP, "bullet"),
        (cc_zip or cache_dir / CC_ZIP, "cartridge"),
    ]
    # Enumerate every .x3p member up front so progress totals are accurate.
    members: list[tuple[Path, str]] = []
    for zip_path, _entity in archives:
        if not zip_path.exists():
            raise FileNotFoundError(
                f"virtual-kits archive not found at {zip_path}. Download the dataset "
                f"first (figshare article {ARTICLE_ID})."
            )
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".x3p"):
                    members.append((zip_path, name))
    if limit is not None:
        members = members[:limit]
    stats["files"] = len(members)
    total = len(members)

    # Group members by archive so each zip is opened once.
    by_zip: dict[Path, list[str]] = {}
    for zip_path, name in members:
        by_zip.setdefault(zip_path, []).append(name)

    index = 0
    for zip_path, names in by_zip.items():
        with zipfile.ZipFile(zip_path) as zf:
            for name in names:
                index += 1
                fname = Path(name).name
                parsed = parse_name(fname)
                row = inventory.get(fname)
                if parsed is None:
                    stats["skipped_unparsed"] += 1
                elif row is None:
                    stats["skipped_no_inventory"] += 1
                else:
                    source_ref = f"{DOI_URL}#{fname}"
                    already = session.exec(
                        select(models.Scan).where(models.Scan.source_ref == source_ref)
                    ).first()
                    if already is not None:
                        stats["already_present"] += 1  # resume: don't re-read bytes
                    else:
                        try:
                            _catalog_one(
                                session,
                                store,
                                study,
                                instruments,
                                parsed,
                                row,
                                zf.read(name),
                                fname=fname,
                                source_ref=source_ref,
                            )
                        except (ValueError, OSError):
                            if not continue_on_error:
                                raise
                            session.rollback()
                            stats["failed"] += 1
                        else:
                            stats["ingested"] += 1
                if on_progress:
                    on_progress(index, total, fname)
    return stats


# --------------------------------------------------------------------------- #
# Download (streaming — never loads a multi-GB zip into memory)               #
# --------------------------------------------------------------------------- #
def _discover_files() -> dict[str, dict]:
    """Map ``{filename: file-record}`` for the figshare article."""
    import httpx

    resp = httpx.get(f"{FIGSHARE_API}/articles/{ARTICLE_ID}", timeout=120.0)
    resp.raise_for_status()
    return {f["name"]: f for f in resp.json().get("files", [])}


def _stream_download(
    url: str,
    dest: Path,
    *,
    expected_size: int | None,
    expected_md5: str | None,
    on_bytes: Callable[[int, int | None], None] | None = None,
) -> None:
    """Stream ``url`` to ``dest`` in chunks, verifying size + MD5 on completion.

    Writes to a sibling temp file and atomically renames, so an interrupted
    download never leaves a corrupt cache entry that a resume would trust.
    """
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".part")
    md5 = hashlib.md5()
    received = 0
    try:
        with (
            os.fdopen(fd, "wb") as fh,
            httpx.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=None,
                headers={"User-Agent": USER_AGENT},
            ) as resp,
        ):
            resp.raise_for_status()
            for chunk in resp.iter_bytes(chunk_size=1 << 20):
                fh.write(chunk)
                md5.update(chunk)
                received += len(chunk)
                if on_bytes:
                    on_bytes(received, expected_size)
        if expected_size is not None and received != expected_size:
            raise OSError(f"size mismatch for {dest.name}: got {received}, want {expected_size}")
        if expected_md5 and md5.hexdigest() != expected_md5:
            raise OSError(f"MD5 mismatch for {dest.name}")
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def download_dataset(
    cache_dir: Path = CACHE_DIR,
    *,
    names: tuple[str, ...] = (INVENTORY_CSV, BU_ZIP, CC_ZIP),
    on_progress: Callable[[str, int, int | None], None] | None = None,
) -> dict[str, Path]:
    """Download the requested dataset files into ``cache_dir`` (skipping any that
    are already present at the expected size). Returns ``{name: path}``."""
    records = _discover_files()
    paths: dict[str, Path] = {}
    for name in names:
        rec = records.get(name)
        if rec is None:
            raise FileNotFoundError(f"figshare article {ARTICLE_ID} has no file {name!r}")
        dest = cache_dir / name
        size = rec.get("size")
        if dest.exists() and (size is None or dest.stat().st_size == size):
            paths[name] = dest
            continue
        _stream_download(
            rec["download_url"],
            dest,
            expected_size=size,
            expected_md5=rec.get("computed_md5") or rec.get("supplied_md5"),
            on_bytes=(lambda r, t, _n=name: on_progress(_n, r, t)) if on_progress else None,
        )
        paths[name] = dest
    return paths
