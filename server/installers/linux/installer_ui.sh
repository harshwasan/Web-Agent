#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_SCRIPT="${SCRIPT_DIR}/install_webagent_bridge.sh"
PACKAGED_UNINSTALL_SCRIPT="${SCRIPT_DIR}/uninstall_webagent_bridge.sh"
INSTALLED_UNINSTALL_SCRIPT="${HOME}/.local/share/WebAgentBridge/uninstall_webagent_bridge.sh"
IS_INSTALLED="0"
if [[ -x "${HOME}/.local/share/WebAgentBridge/WebAgentBridge" ]]; then
  IS_INSTALLED="1"
fi

run_install() {
  bash "${INSTALL_SCRIPT}"
}

run_uninstall() {
  if [[ -x "${INSTALLED_UNINSTALL_SCRIPT}" ]]; then
    bash "${INSTALLED_UNINSTALL_SCRIPT}"
  else
    bash "${PACKAGED_UNINSTALL_SCRIPT}"
  fi
}

if command -v zenity >/dev/null 2>&1; then
  OPTIONS=("Install" "Uninstall")
  if [[ "${IS_INSTALLED}" == "1" ]]; then
    OPTIONS=("Reinstall" "Uninstall")
  fi
  CHOICE="$(zenity --list --title="WebAgent Bridge Setup" --text="Choose an action" --column="Action" "${OPTIONS[@]}" --height=240 --width=320 || true)"
  case "${CHOICE}" in
    Install|Reinstall)
      run_install
      zenity --info --title="WebAgent Bridge Setup" --text="WebAgent Bridge installed successfully." || true
      ;;
    Uninstall)
      run_uninstall
      zenity --info --title="WebAgent Bridge Setup" --text="WebAgent Bridge removed successfully." || true
      ;;
    *)
      exit 0
      ;;
  esac
  exit 0
fi

echo "WebAgent Bridge Setup"
echo "====================="
echo "1) $( [[ "${IS_INSTALLED}" == "1" ]] && echo "Reinstall" || echo "Install" )"
echo "2) Uninstall"
echo "3) Exit"
printf "Choose an option: "
read -r choice
case "${choice}" in
  1)
    run_install
    ;;
  2)
    run_uninstall
    ;;
  *)
    exit 0
    ;;
esac
