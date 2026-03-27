#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT}/dist/linux"
PAYLOAD_DIR="${ROOT}/build/.installer-linux/payload"
SETUP_NAME="WebAgentBridgeSetup"
ARCHIVE_PATH="${DIST_DIR}/${SETUP_NAME}.tar.gz"

mkdir -p "${PAYLOAD_DIR}" "${DIST_DIR}"
rm -rf "${PAYLOAD_DIR:?}"/*

if [[ ! -f "${DIST_DIR}/WebAgentBridge" ]]; then
  echo "Built Linux binary not found at ${DIST_DIR}/WebAgentBridge" >&2
  echo "Run ./build/build_linux.sh first on a Linux machine." >&2
  exit 1
fi

cp "${DIST_DIR}/WebAgentBridge" "${PAYLOAD_DIR}/WebAgentBridge"
cp "${ROOT}/installers/linux/install_webagent_bridge.sh" "${PAYLOAD_DIR}/install_webagent_bridge.sh"
cp "${ROOT}/installers/linux/uninstall_webagent_bridge.sh" "${PAYLOAD_DIR}/uninstall_webagent_bridge.sh"
cp "${ROOT}/installers/linux/installer_ui.sh" "${PAYLOAD_DIR}/installer_ui.sh"
chmod +x "${PAYLOAD_DIR}/WebAgentBridge" "${PAYLOAD_DIR}/install_webagent_bridge.sh" "${PAYLOAD_DIR}/uninstall_webagent_bridge.sh" "${PAYLOAD_DIR}/installer_ui.sh"

tar -czf "${ARCHIVE_PATH}" -C "${PAYLOAD_DIR}" .
echo "Built Linux setup bundle at ${ARCHIVE_PATH}"
