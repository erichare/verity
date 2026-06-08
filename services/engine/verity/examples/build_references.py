"""One entrypoint to regenerate every bundled calibration reference — ``.npz`` (scores,
labels, cluster IDs) + provenance sidecar — deterministically.

    cd services/engine && uv run verity-build-references [--write]

Without ``--write`` it is a dry run: each reference is rebuilt and its diagnostics
printed, but nothing is saved — so you can confirm the numbers reproduce before
promoting. The ``--write`` flag (read by each builder from ``sys.argv``) saves all three.
"""

from __future__ import annotations

from . import (
    build_bullet_pooled_reference,
    build_cartridge_fadul_reference,
    build_striated_land_reference,
)


def main() -> None:
    print("== bullet-pooled (multi-land striated reference) ==")
    build_bullet_pooled_reference.build()
    print("\n== cartridge-fadul (impressed reference) ==")
    build_cartridge_fadul_reference.build()
    print("\n== striated single-land reference ==")
    build_striated_land_reference.main()


if __name__ == "__main__":
    main()
