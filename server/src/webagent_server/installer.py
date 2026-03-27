from __future__ import annotations

import json
import os
import plistlib
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


APP_NAME = "WebAgent Bridge"
SCHEME = "webagent"


def _python_launcher() -> str:
    exe = Path(sys.executable)
    if os.name == "nt" and exe.name.lower() == "python.exe":
        candidate = exe.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def _desktop_command_parts() -> list[str]:
    return [_python_launcher(), "-m", "webagent_server.desktop_app"]


def _quote_arg(value: str) -> str:
    if os.name == "nt":
        return '"' + str(value).replace('"', '\\"') + '"'
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def _run_quiet(args: list[str]) -> bool:
    try:
        subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _windows_reg_content(command: str) -> str:
    return (
        "Windows Registry Editor Version 5.00\n\n"
        "[HKEY_CURRENT_USER\\Software\\Classes\\webagent]\n"
        "@=\"URL:WebAgent Protocol\"\n"
        "\"URL Protocol\"=\"\"\n\n"
        "[HKEY_CURRENT_USER\\Software\\Classes\\webagent\\DefaultIcon]\n"
        "@=\"%s\"\n\n"
        "[HKEY_CURRENT_USER\\Software\\Classes\\webagent\\shell]\n\n"
        "[HKEY_CURRENT_USER\\Software\\Classes\\webagent\\shell\\open]\n\n"
        "[HKEY_CURRENT_USER\\Software\\Classes\\webagent\\shell\\open\\command]\n"
        "@=\"%s\"\n"
    ) % (_python_launcher().replace("\\", "\\\\"), command.replace("\\", "\\\\").replace('"', '\\"'))


def write_windows_reg_file(output_path: Optional[str] = None) -> str:
    command = " ".join([_quote_arg(part) for part in _desktop_command_parts()] + ['"%1"'])
    target = Path(output_path).expanduser() if output_path else (Path.cwd() / "webagent_protocol_fallback.reg")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_windows_reg_content(command), encoding="utf-16")
    return str(target)


def _windows_install() -> Dict[str, str]:
    import winreg

    command = " ".join([_quote_arg(part) for part in _desktop_command_parts()] + ['"%1"'])
    root = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\webagent")
    winreg.SetValueEx(root, "", 0, winreg.REG_SZ, "URL:WebAgent Protocol")
    winreg.SetValueEx(root, "URL Protocol", 0, winreg.REG_SZ, "")
    icon_key = winreg.CreateKey(root, r"DefaultIcon")
    winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, _python_launcher())
    command_key = winreg.CreateKey(root, r"shell\open\command")
    winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)
    for key in (command_key, icon_key, root):
        try:
            winreg.CloseKey(key)
        except Exception:
            pass
    return {"platform": "windows", "command": command, "registry_root": r"HKCU\Software\Classes\webagent"}


def _linux_install() -> Dict[str, str]:
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = apps_dir / "webagent-bridge.desktop"
    exec_line = " ".join([_quote_arg(part) for part in _desktop_command_parts()] + ["%u"])
    desktop_file.write_text(
        "\n".join([
            "[Desktop Entry]",
            "Name=%s" % APP_NAME,
            "Comment=Local companion app for the WebAgent widget",
            "Type=Application",
            "Terminal=false",
            "Exec=%s" % exec_line,
            "MimeType=x-scheme-handler/%s;" % SCHEME,
            "Categories=Utility;",
        ]) + "\n",
        encoding="utf-8",
    )
    _run_quiet(["update-desktop-database", str(apps_dir)])
    _run_quiet(["xdg-mime", "default", desktop_file.name, "x-scheme-handler/%s" % SCHEME])
    return {"platform": "linux", "desktop_file": str(desktop_file), "exec": exec_line}


def _macos_install() -> Dict[str, str]:
    apps_dir = Path.home() / "Applications"
    app_dir = apps_dir / (APP_NAME + ".app")
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    script_path = macos_dir / "webagent-bridge"
    script_path.write_text(
        "#!/bin/sh\nexec %s -m webagent_server.desktop_app \"$@\"\n" % _quote_arg(_python_launcher()),
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    plist_path = contents_dir / "Info.plist"
    plist_data = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "com.webagent.bridge",
        "CFBundleVersion": "1.0.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "webagent-bridge",
        "LSMinimumSystemVersion": "10.13",
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "WebAgent Protocol",
                "CFBundleURLSchemes": [SCHEME],
            }
        ],
    }
    with plist_path.open("wb") as fh:
        plistlib.dump(plist_data, fh)
    lsregister = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if Path(lsregister).exists():
        _run_quiet([lsregister, "-f", str(app_dir)])
    return {"platform": "macos", "app_bundle": str(app_dir), "launcher": str(script_path)}


def install_protocol_handler() -> Dict[str, str]:
    if os.name == "nt":
        return _windows_install()
    if sys.platform == "darwin":
        return _macos_install()
    return _linux_install()


def main(argv: Optional[list[str]] = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    command = args[0] if args else "install-protocol"
    if command in ("write-reg", "reg"):
        path = write_windows_reg_file(args[1] if len(args) > 1 else None)
        result = {"ok": True, "platform": "windows", "reg_file": path}
    else:
        if command not in ("install-protocol", "install"):
            raise SystemExit("Usage: local-agent-bridge-install [install-protocol|write-reg [output.reg]]")
        result = install_protocol_handler()
    print(json.dumps({"ok": True, **result}, indent=2))
