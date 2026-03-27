from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs, quote, urlparse

import requests

from .server import DATA_DIR, _hidden_subprocess_kwargs


def bridge_base_url() -> str:
    public_base = str(os.getenv("WEBAGENT_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if public_base:
        return public_base
    host = str(os.getenv("WEBAGENT_HOST", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("WEBAGENT_PORT", "8787") or 8787)
    return "http://%s:%d" % (host, port)


def bridge_health_url() -> str:
    return bridge_base_url() + "/healthz"


def bridge_shutdown_url() -> str:
    return bridge_base_url() + "/bridge/shutdown"


def bridge_sites_url(origin: str = "") -> str:
    if origin:
        return bridge_base_url() + "/bridge/sites?origin=" + quote(origin, safe="")
    return bridge_base_url() + "/bridge/sites"


def approved_origins_file_path() -> str:
    return str(DATA_DIR / "approved_origins.json")


def approval_logs_dir_path() -> str:
    return str(DATA_DIR / "approval_logs")


def runtime_logs_dir_path() -> str:
    path = DATA_DIR / "runtime_logs"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def bridge_server_log_path() -> str:
    return str(Path(runtime_logs_dir_path()) / "bridge_server.log")


def desktop_app_log_path() -> str:
    return str(Path(runtime_logs_dir_path()) / "desktop_app.log")


def append_runtime_log(filename: str, message: str) -> None:
    try:
        path = Path(runtime_logs_dir_path()) / filename
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write("[%s] %s\n" % (timestamp, str(message or "").rstrip()))
    except Exception:
        pass


def bridge_running(timeout_seconds: float = 0.75) -> bool:
    try:
        response = requests.get(bridge_health_url(), timeout=timeout_seconds)
        return response.ok
    except Exception:
        return False


def start_bridge_process() -> subprocess.Popen:
    env = os.environ.copy()
    package_root = Path(__file__).resolve().parents[2]
    src_root = str(Path(__file__).resolve().parents[1])
    existing_path = str(env.get("PYTHONPATH", "") or "").strip()
    env["PYTHONPATH"] = src_root + (os.pathsep + existing_path if existing_path else "")
    log_path = bridge_server_log_path()
    append_runtime_log("desktop_app.log", "Starting local bridge process")
    command = [sys.executable, "-m", "webagent_server"]
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--bridge-server"]
    log_handle = open(log_path, "ab")
    return subprocess.Popen(
        command,
        cwd=str(package_root),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        text=False,
        **_hidden_subprocess_kwargs(),
    )


def ensure_bridge_running(wait_seconds: float = 10.0) -> bool:
    if bridge_running():
        return True
    start_bridge_process()
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if bridge_running():
            return True
        time.sleep(0.3)
    return False


def stop_bridge(timeout_seconds: float = 5.0) -> bool:
    if not bridge_running(timeout_seconds=0.5):
        return True
    try:
        requests.post(bridge_shutdown_url(), timeout=1.5)
    except Exception:
        pass
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not bridge_running(timeout_seconds=0.5):
            return True
        time.sleep(0.25)
    return False


def parse_protocol_url(raw_url: str) -> Dict[str, str]:
    parsed = urlparse(str(raw_url or "").strip())
    action = (parsed.netloc or parsed.path.lstrip("/")).strip().lower()
    params = parse_qs(parsed.query or "", keep_blank_values=False)
    origin = str((params.get("origin") or [""])[0] or "").strip()
    return {"action": action, "origin": origin}


def protocol_target_url(protocol_data: Dict[str, str]) -> str:
    action = str(protocol_data.get("action") or "").strip().lower()
    origin = str(protocol_data.get("origin") or "").strip()
    if action in ("approve-site", "approve", "open-bridge"):
        return bridge_sites_url(origin)
    return bridge_sites_url()


def open_browser_url(url: str) -> bool:
    if not url:
        return False
    try:
        return bool(webbrowser.open(url, new=1))
    except Exception:
        return False
