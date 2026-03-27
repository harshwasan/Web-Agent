#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="WebAgent Bridge"
INSTALL_ROOT="${HOME}/.local/share/WebAgentBridge"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${APPS_DIR}/webagent-bridge.desktop"
TARGET_BIN="${INSTALL_ROOT}/WebAgentBridge"
WRAPPER_BIN="${BIN_DIR}/webagent-bridge"
UNINSTALL_SCRIPT="${INSTALL_ROOT}/uninstall_webagent_bridge.sh"
SOURCE_BIN="${SCRIPT_DIR}/WebAgentBridge"
SOURCE_UNINSTALL="${SCRIPT_DIR}/uninstall_webagent_bridge.sh"

if [[ ! -f "${SOURCE_BIN}" ]]; then
  echo "WebAgentBridge binary not found next to installer script." >&2
  exit 1
fi

mkdir -p "${INSTALL_ROOT}" "${BIN_DIR}" "${APPS_DIR}"
cp "${SOURCE_BIN}" "${TARGET_BIN}"
chmod +x "${TARGET_BIN}"

if [[ -f "${SOURCE_UNINSTALL}" ]]; then
  cp "${SOURCE_UNINSTALL}" "${UNINSTALL_SCRIPT}"
  chmod +x "${UNINSTALL_SCRIPT}"
fi

cat > "${WRAPPER_BIN}" <<EOF
#!/usr/bin/env bash
exec "${TARGET_BIN}" "\$@"
EOF
chmod +x "${WRAPPER_BIN}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_NAME}
Comment=Local companion app for the WebAgent browser widget
Exec=${TARGET_BIN} --tray
Icon=utilities-terminal
Terminal=false
Categories=Utility;Network;
MimeType=x-scheme-handler/webagent;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi

if command -v xdg-mime >/dev/null 2>&1; then
  xdg-mime default webagent-bridge.desktop x-scheme-handler/webagent >/dev/null 2>&1 || true
fi

nohup "${TARGET_BIN}" --tray >/dev/null 2>&1 &

echo
echo "Installed ${APP_NAME}"
echo "  Binary: ${TARGET_BIN}"
echo "  Desktop file: ${DESKTOP_FILE}"
echo "  Wrapper: ${WRAPPER_BIN}"
