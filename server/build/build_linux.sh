#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m pip install -e ".[build]"
python -m PyInstaller --noconfirm --clean "./build/pyinstaller_webagent_bridge.spec" --distpath "./dist/linux" --workpath "./build/.pyinstaller-linux"
chmod +x "./dist/linux/WebAgentBridge" 2>/dev/null || true

echo "Built Linux app under server/dist/linux"
