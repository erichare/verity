"""Build self-contained Claude Code and Codex ZIPs using only the Python stdlib."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"claude": ".claude-plugin", "codex": ".codex-plugin"}


def image_assets(target: str, manifest: dict) -> list[str]:
    """Include only the local image paths explicitly declared by the manifest."""
    paths = [manifest.get("icon")] if target == "claude" else [
        manifest.get("interface", {}).get(key) for key in ("logo", "composerIcon")
    ]
    names = set()
    for value in paths:
        if value is None:
            continue
        if not isinstance(value, str) or not value.startswith("./") or "\\" in value:
            raise ValueError("Plugin image must be a local ./ path")
        path = PurePosixPath(value)
        if ".." in path.parts or path.suffix.lower() not in {".png", ".svg"}:
            raise ValueError(f"Unsupported plugin image path: {value}")
        names.add(path.as_posix())
    return sorted(names)


def standalone_marketplace(target: str) -> tuple[str, bytes]:
    """Let an extracted ZIP be installed without cloning the entire monorepo."""
    name = ".claude-plugin/marketplace.json" if target == "claude" else ".agents/plugins/marketplace.json"
    marketplace = json.loads((ROOT / name).read_text())
    marketplace["plugins"][0]["source"] = "./" if target == "claude" else {
        "source": "local", "path": "./"
    }
    return name, (json.dumps(marketplace, indent=2) + "\n").encode()


def package_files(target: str) -> list[tuple[str, Path]]:
    """An explicit allowlist keeps local caches and credentials out of the ZIP."""
    root = ROOT / "plugins" / target
    manifest = json.loads((root / TARGETS[target] / "plugin.json").read_text())
    names = [f"{TARGETS[target]}/plugin.json", ".mcp.json", "README.md"]
    names += sorted(p.relative_to(root).as_posix() for p in (root / "skills").rglob("*.md"))
    names += image_assets(target, manifest)
    files = [(name, root / name) for name in names]
    for name, path in files:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Package file escapes plugin: {name}")
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != ROOT and parent.is_relative_to(ROOT)):
            raise ValueError(f"Symlinked package path: {name}")
    files += [(name, ROOT / name) for name in ("LICENSE-MIT", "LICENSE-APACHE")]
    for name, path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or symlinked package file: {name}")
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Package file escapes repository: {name}")
    return files


def build(target: str, output: Path) -> Path:
    root = ROOT / "plugins" / target
    manifest = json.loads((root / TARGETS[target] / "plugin.json").read_text())
    version = manifest["version"]
    if not isinstance(version, str) or not version or any(c not in "0123456789." for c in version):
        raise ValueError("Plugin version must be a numeric dotted version")
    files = package_files(target)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"verity-{target}-{version}.zip"
    contents = [(name, path.read_bytes()) for name, path in files]
    contents.append(standalone_marketplace(target))
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in contents:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "plugins")
    args = parser.parse_args()
    checksums = []
    for target in TARGETS:
        archive = build(target, args.output)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {archive.name}")
        print(archive)
    (args.output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")


if __name__ == "__main__":
    main()
