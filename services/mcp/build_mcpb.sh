#!/usr/bin/env bash
# Build verity-forensics.mcpb — a one-click Claude Desktop extension bundle.
#
# Bundles the server package + its dependencies into a flat layout and zips it with the
# manifest, per the MCP Bundle (.mcpb) spec. Install by double-clicking the .mcpb in
# Claude Desktop (it will prompt for the API URL).
#
#   bash build_mcpb.sh
set -euo pipefail
cd "$(dirname "$0")"

BUILD=".mcpb-build"
OUT="verity-forensics.mcpb"

rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD/lib"

cp manifest.json "$BUILD/"
cp -r verity_mcp "$BUILD/verity_mcp"

# Flat dependency tree next to the package (no venv inside the bundle).
python -m pip install --quiet --target "$BUILD/lib" "mcp>=1.2" "requests>=2.31"

( cd "$BUILD" && zip -qr "../$OUT" manifest.json verity_mcp lib )
rm -rf "$BUILD"
echo "wrote $OUT — double-click it in Claude Desktop to install."
