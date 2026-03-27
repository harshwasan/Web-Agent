#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${HOME}/.local/share/WebAgentBridge"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${APPS_DIR}/webagent-bridge.desktop"
WRAPPER_BIN="${BIN_DIR}/webagent-bridge"

pkill -f "WebAgentBridge" >/dev/null 2>&1 || true

rm -f "${WRAPPER_BIN}"
rm -f "${DESKTOP_FILE}"
rm -rf "${INSTALL_ROOT}"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi

echo
echo "Removed WebAgent Bridge"
