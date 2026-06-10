"""``/benchmark`` — the open, frozen, source-disjoint benchmark.

* ``GET  /benchmark/splits`` — the frozen splits.
* ``GET  /benchmark/splits/{name}`` — protocol + provenance + ``split_hash``.
* ``GET  /benchmark/splits/{name}/kit`` — the replication kit (zip): frozen
  pairs, folds, provenance, the scorer, and a standalone ``evaluate.py`` whose
  offline output equals the leaderboard scoring.
* ``GET  /benchmark/splits/{name}/leaderboard`` — submissions ranked by
  **calibration loss** (Cllr − Cllr_min), the LR-quality axis.
* ``POST /benchmark/splits/{name}/submissions`` — submit one LR per frozen
  pair; scored server-side with the same scorer the kit ships. Rate-limited;
  honor-system (the labels are public — this is a replication benchmark, not a
  blind contest, and the contract asks for source-disjoint calibration).
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from collections import deque

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, func, select

from ... import models
from ...benchmark.kit import build_kit
from ...benchmark.scoring import score_submission, validate_lrs
from ..deps import get_session
from ..envelope import Envelope, ok
from ..schemas import (
    BenchmarkSplitDetail,
    BenchmarkSplitSummary,
    BenchmarkSubmissionRequest,
    BenchmarkSubmissionResult,
    LeaderboardEntry,
)

router = APIRouter(prefix="/benchmark", tags=["benchmark"])

# --- Submission rate limiting (sliding window per client IP) ----------------- #
_RATE_LIMIT = int(os.environ.get("VERITY_BENCHMARK_RATE_LIMIT", "5"))
_RATE_WINDOW_S = float(os.environ.get("VERITY_BENCHMARK_RATE_WINDOW_S", "3600"))
_TRUST_PROXY = os.environ.get("VERITY_TRUST_PROXY_HEADERS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_MAX_TRACKED_IPS = 10_000
_rate_hits: dict[str, deque] = {}


def _client_ip(request: Request) -> str:
    if _TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "anonymous"


def _rate_limited(request: Request) -> None:
    ip = _client_ip(request)
    now = time.monotonic()
    hits = _rate_hits.get(ip)
    if hits is None:
        if len(_rate_hits) > _MAX_TRACKED_IPS:
            stale = [k for k, h in _rate_hits.items() if not h or now - h[-1] > _RATE_WINDOW_S]
            for key in stale:
                del _rate_hits[key]
        hits = _rate_hits[ip] = deque()
    while hits and now - hits[0] > _RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="submission rate limit exceeded; slow down")
    hits.append(now)


def _maybe_require_token(request: Request) -> None:
    """If ``VERITY_BENCHMARK_SUBMIT_TOKEN`` is set, submissions must carry it in
    ``X-Benchmark-Token`` — a soft close valve if the open leaderboard is abused."""
    token = os.environ.get("VERITY_BENCHMARK_SUBMIT_TOKEN", "")
    if token and request.headers.get("x-benchmark-token") != token:
        raise HTTPException(status_code=403, detail="submissions currently require a token")


def _get_split(session: Session, name: str) -> models.BenchmarkSplit:
    split = session.exec(
        select(models.BenchmarkSplit).where(models.BenchmarkSplit.name == name)
    ).first()
    if split is None:
        raise HTTPException(status_code=404, detail=f"benchmark split {name!r} not found")
    return split


def _require_complete_pairs(session: Session, split: models.BenchmarkSplit) -> None:
    """The kit and submission scoring are only meaningful against the *complete*
    frozen pair set. A partial load (e.g. metadata published before the bulk
    pair load) must fail loudly, never serve a silently-truncated benchmark."""
    n = session.exec(
        select(func.count())
        .select_from(models.BenchmarkPair)
        .where(models.BenchmarkPair.split_id == split.id)
    ).one()
    if int(n) != split.n_pairs:
        raise HTTPException(
            status_code=503,
            detail=(
                f"split {split.name!r} is not fully published yet "
                f"({int(n)}/{split.n_pairs} pairs loaded) — try again later"
            ),
        )


@router.get(
    "/splits",
    summary="List the frozen benchmark splits",
    response_model=Envelope[list[BenchmarkSplitSummary]],
)
def list_splits(session: Session = Depends(get_session)) -> Envelope[list[BenchmarkSplitSummary]]:
    splits = session.exec(
        select(models.BenchmarkSplit).order_by(models.BenchmarkSplit.name)
    ).all()
    return ok([BenchmarkSplitSummary.model_validate(s) for s in splits])


@router.get(
    "/splits/{name}",
    summary="A split's protocol, provenance, and split_hash",
    response_model=Envelope[BenchmarkSplitDetail],
)
def get_split(name: str, session: Session = Depends(get_session)) -> Envelope[BenchmarkSplitDetail]:
    split = _get_split(session, name)
    n_submissions = session.exec(
        select(func.count())
        .select_from(models.BenchmarkSubmission)
        .where(models.BenchmarkSubmission.split_id == split.id)
    ).one()
    detail = BenchmarkSplitDetail(
        **BenchmarkSplitSummary.model_validate(split).model_dump(),
        provenance=json.loads(split.provenance),
        n_submissions=int(n_submissions),
    )
    return ok(detail)


@router.get(
    "/splits/{name}/kit",
    summary="Download the replication kit (zip)",
    response_class=Response,
)
def get_kit(name: str, session: Session = Depends(get_session)) -> Response:
    """Frozen pairs + folds + provenance + the scorer + a standalone
    ``evaluate.py``. Offline evaluation equals the leaderboard scoring."""
    split = _get_split(session, name)
    _require_complete_pairs(session, split)
    pairs = session.exec(
        select(models.BenchmarkPair)
        .where(models.BenchmarkPair.split_id == split.id)
        .order_by(models.BenchmarkPair.id)
    ).all()
    data = build_kit(split, pairs)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="verity-benchmark-{split.name}.zip"',
            "ETag": f'"{split.split_hash}"',
        },
    )


@router.get(
    "/splits/{name}/leaderboard",
    summary="Submissions ranked by Cllr (calibration loss highlighted)",
    response_model=Envelope[list[LeaderboardEntry]],
)
def leaderboard(
    name: str, session: Session = Depends(get_session)
) -> Envelope[list[LeaderboardEntry]]:
    """Ranked by total ``Cllr`` — the proper scoring rule. Calibration loss is
    the highlighted axis but cannot be the sort key: the uninformative LR=1
    submission has *zero* calibration loss (Cllr = Cllr_min = 1), so ranking by
    loss alone would crown triviality."""
    split = _get_split(session, name)
    subs = session.exec(
        select(models.BenchmarkSubmission)
        .where(models.BenchmarkSubmission.split_id == split.id)
        .order_by(models.BenchmarkSubmission.cllr)
        .limit(100)
    ).all()
    return ok([LeaderboardEntry.model_validate(s) for s in subs])


def _parse_lrs(body: BenchmarkSubmissionRequest) -> dict[str, float]:
    if (body.lrs is None) == (body.csv is None):
        raise HTTPException(
            status_code=422, detail="provide exactly one of 'lrs' (object) or 'csv' (string)"
        )
    if body.lrs is not None:
        return dict(body.lrs)
    reader = csv.DictReader(io.StringIO(body.csv))
    if not reader.fieldnames or "pair_id" not in reader.fieldnames or "lr" not in reader.fieldnames:
        raise HTTPException(status_code=422, detail="csv needs a 'pair_id,lr' header")
    try:
        return {row["pair_id"]: float(row["lr"]) for row in reader}
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"unparseable LR value: {exc}") from exc


@router.post(
    "/splits/{name}/submissions",
    summary="Submit one LR per frozen pair; scored server-side",
    response_model=Envelope[BenchmarkSubmissionResult],
    status_code=201,
)
def submit(
    name: str,
    body: BenchmarkSubmissionRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> Envelope[BenchmarkSubmissionResult]:
    _maybe_require_token(request)
    _rate_limited(request)
    split = _get_split(session, name)
    _require_complete_pairs(session, split)
    lrs_by_id = _parse_lrs(body)

    rows = session.exec(
        select(
            models.BenchmarkPair.pair_id, models.BenchmarkPair.label, models.BenchmarkPair.folds
        )
        .where(models.BenchmarkPair.split_id == split.id)
        .order_by(models.BenchmarkPair.id)
    ).all()
    wanted = {r[0] for r in rows}
    missing = wanted - set(lrs_by_id)
    unknown = set(lrs_by_id) - wanted
    if missing or unknown:
        raise HTTPException(
            status_code=422,
            detail=(
                f"coverage mismatch: {len(missing)} pair(s) missing, {len(unknown)} unknown "
                "pair id(s) — submit exactly one LR per frozen pair (see the kit)"
            ),
        )

    lrs = np.array([lrs_by_id[r[0]] for r in rows])
    problems = validate_lrs(lrs)
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))
    labels = np.array([r[1] for r in rows], dtype=float)
    fold_members: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        for f in (r[2] or "").split(";"):
            if f:
                fold_members.setdefault(int(f), []).append(i)
    folds = [(k, np.array(v)) for k, v in sorted(fold_members.items())]

    try:
        metrics = score_submission(lrs, labels, folds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    submission = models.BenchmarkSubmission(
        split_id=split.id,
        submitter=body.submitter.strip(),
        method=body.method.strip(),
        url=body.url,
        is_reference=False,
        cllr=metrics["cllr"],
        cllr_std=metrics["cllr_std"],
        cllr_min=metrics["cllr_min"],
        auc=metrics["auc"],
        calibration_loss=metrics["calibration_loss"],
        metrics=json.dumps(metrics),
    )
    session.add(submission)
    session.commit()

    return ok(
        BenchmarkSubmissionResult(
            split=split.name,
            split_hash=split.split_hash,
            submitter=submission.submitter,
            method=submission.method,
            metrics={k: v for k, v in metrics.items() if k != "folds"},
        )
    )
