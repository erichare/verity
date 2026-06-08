"""Ingest 1-D striated **toolmark** profiles — the catalog's third mark family,
alongside bullet lands (striated) and cartridge marks (impressed).

Toolmark reference sets arrive as extracted 1-D profiles, not 3-D X3P surfaces,
so each mark is stored as a content-addressed little-endian ``float64`` blob with
modality ``profile_1d`` under a ``Study ─< Tool ─< Toolmark ─< Scan`` path.

Ships the **MIT-licensed** ``heike/tmaRks`` set: 580 marks from
consecutively-manufactured slotted screwdrivers (Hofmann et al.; the data behind
Gao & Hofmann 2024). The neutral CSV cache is produced by the engine exporter
``verity-toolmark-tmaRks`` (which fetches ``heike/tmaRks`` at runtime).

The GPL-3 ``ameslab`` screwdriver set is intentionally **not** ingested into this
public catalog — its license forbids redistribution from an MIT/public mirror.
"""

from __future__ import annotations

import array
import csv
import re
import sys
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session, select

from . import models
from .store import BlobStore

TMARKS_CACHE = Path.home() / ".cache" / "verity" / "tmaRks"
TMARKS_LONG_CSV = "toolmarks_long.csv"
TMARKS_SOURCE = "tmarks"
TMARKS_SOURCE_REF = "https://github.com/heike/tmaRks"

# A tmaRks TID is ``<tool><size><side>-F<force>-<rep>`` e.g. ``T01LA-F60-01``.
# The leading token (``T01LA``) is the mark-generating edge; ``T01`` is the tool.
_TID_RE = re.compile(r"^(T\d+)([A-Za-z])([A-Za-z])$")


def _serialize_profile(values: list[float]) -> bytes:
    """Canonical little-endian ``float64`` bytes for a 1-D profile — deterministic
    (same values → same bytes → same content hash), host-endianness-independent."""
    arr = array.array("d", values)
    if sys.byteorder == "big":  # pragma: no cover - normalize to little-endian
        arr.byteswap()
    return arr.tobytes()


def parse_tmarks_tid(tid: str) -> tuple[str, str, str] | None:
    """``"T01LA-F60-01"`` → ``(tool="T01", edge="T01LA", side="A")``; ``None`` if
    the head token doesn't parse."""
    head = tid.split("-")[0]
    m = _TID_RE.match(head)
    if not m:
        return None
    return m.group(1), head, m.group(3)


def load_tmarks_profiles(cache_dir: Path = TMARKS_CACHE) -> OrderedDict[str, list[float]]:
    """Group the long CSV (``TID,value``) into one profile per TID, in file order."""
    grouped: OrderedDict[str, list[float]] = OrderedDict()
    with (cache_dir / TMARKS_LONG_CSV).open() as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for tid, value in reader:
            grouped.setdefault(tid, []).append(float(value))
    return grouped


def get_or_create_tmarks_study(session: Session) -> models.Study:
    study = session.exec(
        select(models.Study).where(
            models.Study.source == TMARKS_SOURCE,
            models.Study.external_id == "tmarks-screwdrivers",
        )
    ).first()
    if study:
        return study
    study = models.Study(
        source=TMARKS_SOURCE,
        external_id="tmarks-screwdrivers",
        title="tmaRks — consecutively-manufactured slotted screwdriver toolmarks",
        creator="H. Hofmann et al. (CSAFE)",
        references="heike/tmaRks (MIT); Gao, Hofmann et al. (2024)",
        persistence=False,
        consecutively_manufactured=True,
        nist_measurement=False,
    )
    session.add(study)
    session.commit()
    session.refresh(study)
    return study


def get_or_create_tool(
    session: Session, study: models.Study, external_id: str, *, kind: str | None = None
) -> models.Tool:
    tool = session.exec(
        select(models.Tool).where(
            models.Tool.study_id == study.id,
            models.Tool.external_id == external_id,
        )
    ).first()
    if tool:
        return tool
    tool = models.Tool(study_id=study.id, external_id=external_id, kind=kind)
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return tool


def get_or_create_toolmark(
    session: Session,
    tool: models.Tool,
    external_id: str,
    *,
    edge: str | None = None,
    side: str | None = None,
    angle_deg: float | None = None,
) -> models.Toolmark:
    toolmark = session.exec(
        select(models.Toolmark).where(
            models.Toolmark.tool_id == tool.id,
            models.Toolmark.external_id == external_id,
        )
    ).first()
    if toolmark:
        return toolmark
    toolmark = models.Toolmark(
        tool_id=tool.id, external_id=external_id, edge=edge, side=side, angle_deg=angle_deg
    )
    session.add(toolmark)
    session.commit()
    session.refresh(toolmark)
    return toolmark


def ingest_tmaRks(
    session: Session,
    store: BlobStore,
    *,
    cache_dir: Path = TMARKS_CACHE,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Ingest the cached tmaRks screwdriver profiles as ``profile_1d`` scans.

    Idempotent: a profile whose content hash is already cataloged is skipped."""
    csv_path = cache_dir / TMARKS_LONG_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"tmaRks profile cache not found at {csv_path}. Produce it with the "
            "engine exporter: `uv run verity-toolmark-tmaRks` (fetches heike/tmaRks, MIT)."
        )

    study = get_or_create_tmarks_study(session)
    profiles = load_tmarks_profiles(cache_dir)
    stats = {"marks": len(profiles), "ingested": 0, "already_present": 0, "skipped": 0}
    total = len(profiles)

    for index, (tid, values) in enumerate(profiles.items(), start=1):
        parsed = parse_tmarks_tid(tid)
        if parsed is None:
            stats["skipped"] += 1
        else:
            tool_extid, edge, side = parsed
            blob = _serialize_profile(values)
            content_hash = store.put(blob)
            existing = session.exec(
                select(models.Scan).where(models.Scan.content_hash == content_hash)
            ).first()
            if existing:
                stats["already_present"] += 1
            else:
                tool = get_or_create_tool(
                    session, study, tool_extid, kind="Slotted screwdriver"
                )
                toolmark = get_or_create_toolmark(
                    session, tool, tid, edge=edge, side=side
                )
                session.add(
                    models.Scan(
                        toolmark_id=toolmark.id,
                        modality="profile_1d",
                        content_hash=content_hash,
                        size_bytes=len(blob),
                        filename=f"{tid}.f64",
                        source=TMARKS_SOURCE,
                        source_ref=TMARKS_SOURCE_REF,
                    )
                )
                session.commit()
                stats["ingested"] += 1
        if on_progress:
            on_progress(index, total, tid)
    return stats
