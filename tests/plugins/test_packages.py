"""Validate the packages users actually install, without a live service or SDK."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_plugins", ROOT / "scripts/build_plugins.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PluginPackages(unittest.TestCase):
    def test_marketplaces_resolve_to_native_packages(self):
        claude = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        codex = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        for target, marketplace in (("claude", claude), ("codex", codex)):
            entry = marketplace["plugins"][0]
            source = entry["source"] if target == "claude" else entry["source"]["path"]
            plugin = (ROOT / source).resolve()
            self.assertTrue(plugin.is_relative_to(ROOT))
            manifest = json.loads((plugin / f".{target}-plugin/plugin.json").read_text())
            self.assertEqual(entry["name"], manifest["name"])
            self.assertEqual(marketplace["name"], "verity")
            if target == "claude":
                self.assertEqual(entry["version"], manifest["version"])

    def test_archives_are_complete_and_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            for target in builder.TARGETS:
                with self.subTest(target=target):
                    archive = builder.build(target, Path(tmp))
                    first = archive.read_bytes()
                    self.assertEqual(first, builder.build(target, Path(tmp)).read_bytes())
                    with zipfile.ZipFile(archive) as bundle:
                        names = set(bundle.namelist())
                        self.assertFalse(any(".." in Path(n).parts or n.startswith("/") for n in names))
                        self.assertIn("LICENSE-MIT", names)
                        self.assertIn("LICENSE-APACHE", names)
                        self.assertIn("README.md", names)
                        manifest = json.loads(bundle.read(f".{target}-plugin/plugin.json"))
                        market_path = ".claude-plugin/marketplace.json" if target == "claude" else ".agents/plugins/marketplace.json"
                        market = json.loads(bundle.read(market_path))
                        source = market["plugins"][0]["source"]
                        self.assertEqual(source if target == "claude" else source["path"], "./")
                        self.assertEqual(market["plugins"][0]["name"], manifest["name"])
                        self.assertIn(manifest["mcpServers"].removeprefix("./"), names)
                        for asset in builder.image_assets(target, manifest):
                            self.assertIn(asset, names)
                            self.assertEqual(bundle.read(asset), (ROOT / "plugins" / target / asset).read_bytes())
                        if target == "claude":
                            png = bundle.read(manifest["icon"].removeprefix("./"))
                            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
                            width, height = struct.unpack(">II", png[16:24])
                            self.assertEqual(width, height)
                            self.assertTrue(512 <= width <= 2048)
                            self.assertLess(len(png), 2 * 1024 * 1024)
                        mcp = json.loads(bundle.read(".mcp.json"))
                        self.assertEqual(mcp["mcpServers"], {
                            "verity": {"type": "http", "url": "https://api.verity.codes/mcp"}
                        })
                        skills = [n for n in names if n.endswith("/SKILL.md")]
                        self.assertEqual(len(skills), 3)
                        for skill in skills:
                            text = bundle.read(skill).decode()
                            self.assertTrue(text.startswith("---\nname: "))
                            self.assertIn("\ndescription: ", text)
                        self.assertIn("skills/explain-result/SKILL.md", names)
                        self.assertFalse(any(n.endswith((".pyc", ".env")) for n in names))

    def test_image_references_reject_external_and_traversal_paths(self):
        for value in ("https://example.com/logo.png", "/tmp/logo.png", "./../logo.png",
                      "./assets/../../logo.png", "./assets\\logo.png", "./assets/config.json", 123):
            for target in builder.TARGETS:
                with self.subTest(target=target, value=value):
                    manifest = {"icon": value} if target == "claude" else {"interface": {"logo": value}}
                    with self.assertRaises(ValueError):
                        builder.image_assets(target, manifest)

    def test_only_referenced_images_are_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            shutil.copytree(ROOT / "plugins/claude", root / "plugins/claude")
            for name in ("LICENSE-MIT", "LICENSE-APACHE"):
                shutil.copyfile(ROOT / name, root / name)
            (root / "plugins/claude/unreferenced.png").write_bytes(b"not a listing asset")
            with patch.object(builder, "ROOT", root):
                names = [name for name, _ in builder.package_files("claude")]
            self.assertIn(".claude-plugin/icon.png", names)
            self.assertNotIn("unreferenced.png", names)

    def test_missing_and_symlinked_images_are_rejected(self):
        for case in ("missing", "file-symlink", "directory-symlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                plugin = root / "plugins/codex"
                shutil.copytree(ROOT / "plugins/codex", plugin)
                for name in ("LICENSE-MIT", "LICENSE-APACHE"):
                    shutil.copyfile(ROOT / name, root / name)
                image = plugin / "assets/icon.svg"
                original = image.read_bytes()
                image.unlink()
                if case == "file-symlink":
                    # Even a target within this plugin must not bypass the allowlist.
                    hidden = plugin / "private.svg"
                    hidden.write_bytes(original)
                    image.symlink_to(hidden)
                elif case == "directory-symlink":
                    (plugin / "assets").rmdir()
                    outside = root / "private"
                    outside.mkdir()
                    (outside / "icon.svg").write_bytes(original)
                    (plugin / "assets").symlink_to(outside, target_is_directory=True)
                with patch.object(builder, "ROOT", root), self.assertRaises(ValueError):
                    builder.package_files("codex")

    def test_workflows_and_connection_do_not_drift_across_hosts(self):
        claude = ROOT / "plugins/claude"
        codex = ROOT / "plugins/codex"
        paths = [Path(".mcp.json"), *[p.relative_to(claude) for p in (claude / "skills").rglob("*.md")]]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual((claude / path).read_bytes(), (codex / path).read_bytes())
        a = json.loads((claude / ".claude-plugin/plugin.json").read_text())
        b = json.loads((codex / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(a["version"], b["version"])


if __name__ == "__main__":
    unittest.main()
