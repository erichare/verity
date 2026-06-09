"""Verity API client — a thin wrapper over the calibrated-LR REST API.

Every comparison returns a reproducible ``recipe`` and a content ``handle``: the same
inputs + scorer config + reference + engine reproduce the same handle, so verifying a
published likelihood ratio is a hash-equality check (see ``clients/README.md`` for a
ten-line example). The client also drives the glass-box step graph
(``upload`` → ``step`` → ``calibrate``) so every intermediate is addressable.

Uses ``requests`` by default; inject any requests-compatible session (e.g. a FastAPI
``TestClient``) for offline testing.

    from verity_client import VerityClient
    v = VerityClient("https://api.verity.codes")
    r = v.compare("impressed", "a.x3p", "b.x3p")
    print(r["likelihood_ratio"], r["recipe"]["handle"])
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_BASE_URL = "https://api.verity.codes"


class VerityError(RuntimeError):
    """A non-2xx response from the Verity API."""


def _aslist(paths: Any) -> list:
    return list(paths) if isinstance(paths, (list, tuple)) else [paths]


def _file_field(path: Any) -> tuple[str, Any]:
    """A multipart file value ``(filename, fileobj)`` for a path or open file."""
    if hasattr(path, "read"):
        return (getattr(path, "name", "scan.x3p"), path)
    return (os.path.basename(str(path)), open(str(path), "rb"))  # noqa: SIM115 - closed by the request


class VerityClient:
    """A client for the Verity calibrated-LR API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, *, session: Any = None) -> None:
        self._base = base_url.rstrip("/")
        if session is None:
            import requests  # lazy: only needed for real HTTP, not for an injected session

            session = requests.Session()
        self._session = session

    # --- transport ---------------------------------------------------------

    def _json(self, resp: Any) -> Any:
        if resp.status_code >= 400:
            raise VerityError(f"{resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def _get(self, path: str, **kw: Any) -> Any:
        return self._json(self._session.get(self._base + path, **kw))

    def _post(self, path: str, **kw: Any) -> Any:
        return self._json(self._session.post(self._base + path, **kw))

    # --- meta --------------------------------------------------------------

    def health(self) -> dict:
        return self._get("/health")

    def scorer_config(self) -> dict:
        """The deployed scorer hyperparameters + ``config_hash``."""
        return self._get("/v1/scorer-config")

    def references(self) -> list[dict]:
        """Every calibration reference + its provenance (scorer hash, datasets, diagnostics)."""
        return self._get("/v1/references")["references"]

    def reference(self, reference_id: str) -> dict:
        return self._get(f"/v1/references/{reference_id}")

    # --- comparison --------------------------------------------------------

    def detect(self, scan: Any) -> dict:
        """Suggest a mark type (striated / impressed) for one scan."""
        return self._post("/detect", files={"scan": _file_field(scan)})

    def compare(
        self,
        domain: str,
        mark_a: Any,
        mark_b: Any,
        *,
        include: str = "calibration,recipe",
        scorer_config: dict | None = None,
    ) -> dict:
        """Compare two marks (each a path or list of land paths) → the calibrated report,
        with the reproducible ``recipe`` + ``handle`` by default. ``scorer_config`` is an
        optional override; if its hash doesn't match the reference's, the API returns the
        raw score with ``calibrated: false`` (the firewall)."""
        files = [("mark_a", _file_field(p)) for p in _aslist(mark_a)]
        files += [("mark_b", _file_field(p)) for p in _aslist(mark_b)]
        data = {"domain": domain, "include": include}
        if scorer_config is not None:
            data["scorer_config"] = json.dumps(scorer_config)
        return self._post("/v1/compare", data=data, files=files)

    # --- the glass-box step graph -----------------------------------------

    def upload(self, scan: Any) -> str:
        """Upload a scan → a content-addressed surface handle (the graph entry point)."""
        return self._post("/v1/artifacts", files={"scan": _file_field(scan)})["handle"]

    def artifact(self, handle: str) -> dict:
        return self._get(f"/v1/artifacts/{handle}")

    def step(self, name: str, **form: Any) -> dict:
        """Run one pipeline step by name (e.g. ``signature``, ``align``, ``features``),
        passing inputs as content handles."""
        return self._post(f"/v1/steps/{name}", data=form)

    def calibrate(
        self,
        score: float,
        reference: str,
        *,
        scorer_config_hash: str | None = None,
        ci: bool = True,
    ) -> dict:
        """Map a score to a bounded LR against a reference. If ``scorer_config_hash`` is
        given and doesn't match the reference's, calibration is refused (the firewall)."""
        data: dict = {"score": score, "reference": reference, "ci": str(ci).lower()}
        if scorer_config_hash:
            data["scorer_config_hash"] = scorer_config_hash
        return self._post("/v1/steps/calibrate", data=data)

    # --- reproducibility ---------------------------------------------------

    def reproduce(self, domain: str, mark_a: Any, mark_b: Any, *, expect_handle: str) -> bool:
        """Re-run a comparison and check its recipe handle matches ``expect_handle`` —
        reproducibility as a one-line hash-equality check."""
        report = self.compare(domain, mark_a, mark_b, include="recipe")
        return report.get("handle") == expect_handle
