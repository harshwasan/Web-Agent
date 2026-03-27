#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m pip install -e ".[build]"
python -m PyInstaller --noconfirm --clean "./build/pyinstaller_webagent_bridge.spec" --distpath "./dist/macos" --workpath "./build/.pyinstaller-macos"

echo "Built macOS app under server/dist/macos"
