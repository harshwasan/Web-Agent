from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from typing import Optional

import requests

try:
    from .bridge_runtime import (
        append_runtime_log,
        approved_origins_file_path,
        bridge_base_url,
        bridge_running,
        bridge_sites_url,
        desktop_app_log_path,
        ensure_bridge_running,
        open_browser_url,
        parse_protocol_url,
        protocol_target_url,
        runtime_logs_dir_path,
        stop_bridge,
    )
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_root = os.path.dirname(current_dir)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from webagent_server.bridge_runtime import (
        append_runtime_log,
        approved_origins_file_path,
        bridge_base_url,
        bridge_running,
        bridge_sites_url,
        desktop_app_log_path,
        ensure_bridge_running,
        open_browser_url,
        parse_protocol_url,
        protocol_target_url,
        runtime_logs_dir_path,
        stop_bridge,
    )


_APP_CONTROL_HOST = "127.0.0.1"
_APP_CONTROL_PORT = int(os.getenv("WEBAGENT_APP_CONTROL_PORT", "8798") or 8798)


def _open_path(path: str) -> None:
    if not path:
        return
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _send_to_running_instance(protocol_url: str = "", show_window: bool = True, timeout_seconds: float = 1.0) -> bool:
    payload = {
        "protocol_url": str(protocol_url or "").strip(),
        "show_window": bool(show_window),
    }
    try:
        with socket.create_connection((_APP_CONTROL_HOST, _APP_CONTROL_PORT), timeout=timeout_seconds) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            return True
    except Exception:
        return False


class BridgeDesktopApp:
    def __init__(self, root, protocol_url: str = "", start_hidden: bool = False) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.tk = tk
        self.ttk = ttk
        self.protocol_url = str(protocol_url or "").strip()
        self.start_hidden = bool(start_hidden)
        self.tray_icon = None
        self.tray_thread = None
        self.tray_enabled = True
        self.tray_supported = False
        self.control_server = None
        self.control_thread = None

        self.root.title("WebAgent Bridge")
        self.root.geometry("560x380")
        self.root.minsize(520, 330)
        self.root.configure(bg="#eef2f8")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._button_bg = "#e8edf5"
        self._button_fg = "#122030"
        self._button_active_bg = "#dbe5f2"
        self._primary_button_bg = "#274e87"
        self._primary_button_active_bg = "#1f3f70"
        self._check_bg = "#eef2f8"

        self.bridge_status_var = tk.StringVar(value="Checking local bridge...")
        self.base_url_var = tk.StringVar(value=bridge_base_url())
        self.codex_var = tk.StringVar(value="Checking Codex...")
        self.claude_var = tk.StringVar(value="Checking Claude...")
        self.protocol_var = tk.StringVar(value=self.protocol_url or "webagent://open-bridge")
        self.tray_var = tk.BooleanVar(value=True)

        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="WebAgent Bridge", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Local companion app for the browser widget", foreground="#5f6f85").pack(anchor="w", pady=(2, 14))

        status_card = ttk.LabelFrame(frame, text="Status", padding=14)
        status_card.pack(fill="x", pady=(0, 14))
        ttk.Label(status_card, textvariable=self.bridge_status_var).pack(anchor="w")
        ttk.Label(status_card, textvariable=self.base_url_var, foreground="#5f6f85").pack(anchor="w", pady=(4, 0))
        ttk.Label(status_card, textvariable=self.codex_var, foreground="#30445f").pack(anchor="w", pady=(8, 0))
        ttk.Label(status_card, textvariable=self.claude_var, foreground="#30445f").pack(anchor="w", pady=(2, 0))

        protocol_card = ttk.LabelFrame(frame, text="Protocol", padding=14)
        protocol_card.pack(fill="x", pady=(0, 14))
        ttk.Label(protocol_card, textvariable=self.protocol_var, foreground="#30445f").pack(anchor="w")
        ttk.Label(
            protocol_card,
            text="Register webagent:// to point at local-agent-bridge-app or local-agent-bridge-protocol.",
            foreground="#5f6f85",
            wraplength=500,
        ).pack(anchor="w", pady=(6, 0))

        controls = tk.Frame(frame, bg="#eef2f8")
        controls.pack(fill="x")
        self._make_button(controls, "Start Bridge", self.start_bridge, primary=True, width=13).pack(side="left")
        self._make_button(controls, "Stop Bridge", self.stop_bridge, width=11).pack(side="left", padx=(8, 0))
        self._make_button(controls, "Open Sites", self.open_sites, width=11).pack(side="left", padx=(8, 0))
        self._make_button(controls, "Open Logs", self.open_logs, width=11).pack(side="left", padx=(8, 0))
        self._make_button(controls, "Copy URL", self.copy_url, width=10).pack(side="left", padx=(8, 0))
        self._make_button(controls, "Refresh", self.refresh_status, width=10).pack(side="right")

        secondary = tk.Frame(frame, bg="#eef2f8")
        secondary.pack(fill="x", pady=(12, 0))
        self._make_button(secondary, "Open Approval Store", self.open_approval_store, width=18).pack(side="left")
        self._make_button(secondary, "Launch Protocol URL", self.launch_protocol, width=18).pack(side="left", padx=(8, 0))
        tk.Checkbutton(
            secondary,
            text="Run in background",
            variable=self.tray_var,
            command=self._sync_tray_setting,
            bg=self._check_bg,
            fg="#122030",
            activebackground=self._check_bg,
            activeforeground="#122030",
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9),
        ).pack(side="right")

        self._init_tray()
        self._start_control_server()
        self.root.after(120, self.start_bridge)
        if self.protocol_url:
            self.root.after(650, self.launch_protocol)
        self.root.after(1500, self.refresh_status)
        if self.start_hidden and self.tray_supported:
            self.root.after(450, self.hide_to_tray)

    def _make_button(self, parent, text: str, command, primary: bool = False, width: int = 12):
        return self.tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            padx=10,
            pady=7,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold" if primary else "normal"),
            bg=self._primary_button_bg if primary else self._button_bg,
            fg="#ffffff" if primary else self._button_fg,
            activebackground=self._primary_button_active_bg if primary else self._button_active_bg,
            activeforeground="#ffffff" if primary else self._button_fg,
        )

    def _sync_tray_setting(self) -> None:
        self.tray_enabled = bool(self.tray_var.get())

    def _init_tray(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:
            self.tray_supported = False
            self.tray_var.set(False)
            self.tray_enabled = False
            return

        image = Image.new("RGBA", (64, 64), (15, 20, 28, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=16, fill=(15, 20, 28, 255))
        draw.rounded_rectangle((18, 18, 46, 46), radius=10, fill=(35, 224, 200, 255))
        draw.rectangle((28, 18, 46, 32), fill=(15, 20, 28, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Open WebAgent Bridge", lambda icon, item: self.show_window()),
            pystray.MenuItem("Open Approved Sites", lambda icon, item: self.open_sites()),
            pystray.MenuItem("Refresh Status", lambda icon, item: self.refresh_status()),
            pystray.MenuItem("Quit", lambda icon, item: self.quit_app()),
        )
        self.tray_icon = pystray.Icon("webagent-bridge", image, "WebAgent Bridge", menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        self.tray_supported = True

    def hide_to_tray(self) -> None:
        if not self.tray_supported or not self.tray_enabled:
            self.root.destroy()
            return
        self.root.withdraw()
        self.bridge_status_var.set("Running in background")

    def show_window(self) -> None:
        self.root.after(0, self._show_window_main_thread)

    def _show_window_main_thread(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def on_close(self) -> None:
        if self.tray_supported and self.tray_enabled:
            self.hide_to_tray()
            return
        self.quit_app()

    def quit_app(self) -> None:
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        if self.control_server is not None:
            try:
                self.control_server.close()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)

    def start_bridge(self) -> None:
        self.bridge_status_var.set("Starting local bridge...")
        append_runtime_log("desktop_app.log", "Start Bridge clicked")

        def work():
            try:
                running = ensure_bridge_running()
                if not running:
                    append_runtime_log("desktop_app.log", "Bridge failed to start")
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge running" if running else "Bridge failed to start"))
            except Exception as exc:
                append_runtime_log("desktop_app.log", "Start Bridge error: %s" % exc)
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge failed to start"))
            self.root.after(0, self.refresh_status)

        threading.Thread(target=work, daemon=True).start()

    def stop_bridge(self) -> None:
        self.bridge_status_var.set("Stopping local bridge...")
        append_runtime_log("desktop_app.log", "Stop Bridge clicked")

        def work() -> None:
            try:
                stopped = stop_bridge()
                if not stopped:
                    append_runtime_log("desktop_app.log", "Bridge did not stop cleanly")
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge stopped" if stopped else "Bridge did not stop"))
            except Exception as exc:
                append_runtime_log("desktop_app.log", "Stop Bridge error: %s" % exc)
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge did not stop"))
            self.root.after(0, self.refresh_status)

        threading.Thread(target=work, daemon=True).start()

    def open_sites(self) -> None:
        self.bridge_status_var.set("Opening approved sites...")
        append_runtime_log("desktop_app.log", "Open Sites clicked")

        def work() -> None:
            try:
                running = ensure_bridge_running()
                if running:
                    open_browser_url(bridge_sites_url())
                else:
                    append_runtime_log("desktop_app.log", "Open Sites failed because bridge did not start")
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge running" if running else "Bridge failed to start"))
            except Exception as exc:
                append_runtime_log("desktop_app.log", "Open Sites error: %s" % exc)
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge failed to start"))
            self.root.after(0, self.refresh_status)

        threading.Thread(target=work, daemon=True).start()

    def open_logs(self) -> None:
        _open_path(runtime_logs_dir_path())

    def open_approval_store(self) -> None:
        _open_path(approved_origins_file_path())

    def copy_url(self) -> None:
        value = bridge_base_url()
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.bridge_status_var.set("Copied bridge URL")

    def launch_protocol(self) -> None:
        raw_url = self.protocol_url or "webagent://open-bridge"
        self.bridge_status_var.set("Launching protocol flow...")
        append_runtime_log("desktop_app.log", "Launch Protocol URL clicked: %s" % raw_url)

        def work() -> None:
            try:
                running = ensure_bridge_running()
                if running:
                    protocol_data = parse_protocol_url(raw_url)
                    open_browser_url(protocol_target_url(protocol_data))
                else:
                    append_runtime_log("desktop_app.log", "Protocol launch failed because bridge did not start")
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge running" if running else "Bridge failed to start"))
            except Exception as exc:
                append_runtime_log("desktop_app.log", "Launch Protocol error: %s" % exc)
                self.root.after(0, lambda: self.bridge_status_var.set("Bridge failed to start"))
            self.root.after(0, lambda: self.protocol_var.set("webagent://open-bridge"))
            self.root.after(0, self.refresh_status)

        self.protocol_url = ""
        threading.Thread(target=work, daemon=True).start()

    def _start_control_server(self) -> None:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((_APP_CONTROL_HOST, _APP_CONTROL_PORT))
            server.listen(5)
            self.control_server = server
        except OSError:
            self.control_server = None
            return

        def worker() -> None:
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    break
                with conn:
                    try:
                        raw = conn.recv(8192).decode("utf-8", errors="replace").strip()
                        payload = json.loads(raw) if raw else {}
                    except Exception:
                        payload = {}
                    self.root.after(0, lambda p=payload: self._handle_control_payload(p))

        self.control_thread = threading.Thread(target=worker, daemon=True)
        self.control_thread.start()

    def _handle_control_payload(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        if data.get("show_window", True):
            self.show_window()
        protocol_url = str(data.get("protocol_url") or "").strip()
        if protocol_url.startswith("webagent://"):
            self.protocol_url = protocol_url
            self.protocol_var.set(protocol_url)
            self.root.after(150, self.launch_protocol)

    def refresh_status(self) -> None:
        def work():
            running = bridge_running()
            codex_text = "Codex: unavailable"
            claude_text = "Claude: unavailable"
            if running:
                try:
                    codex = requests.get(bridge_base_url() + "/api/codex/status", timeout=2.0).json()
                    codex_text = "Codex: " + ("installed" if codex.get("configured") else "missing") + " | " + str(codex.get("version") or codex.get("cli") or "-")
                except Exception:
                    codex_text = "Codex: status check failed"
                try:
                    claude = requests.get(bridge_base_url() + "/api/claude/status", timeout=2.0).json()
                    claude_text = "Claude: " + ("installed" if claude.get("configured") else "missing") + " | " + str(claude.get("version") or claude.get("cli") or "-")
                except Exception:
                    claude_text = "Claude: status check failed"
            status_text = "Bridge running" if running else "Bridge not running"
            if self.tray_supported and self.root.state() == "withdrawn":
                status_text = "Running in background" if running else "Bridge not running"
            self.root.after(0, lambda: self.bridge_status_var.set(status_text))
            self.root.after(0, lambda: self.codex_var.set(codex_text))
            self.root.after(0, lambda: self.claude_var.set(claude_text))

        threading.Thread(target=work, daemon=True).start()


def main(argv: Optional[list[str]] = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    protocol_url = ""
    start_hidden = False
    for arg in args:
        text = str(arg or "")
        if text.startswith("webagent://"):
            protocol_url = text
        elif text in ("--tray", "--background", "--minimized"):
            start_hidden = True
    if _send_to_running_instance(protocol_url=protocol_url, show_window=not start_hidden):
        return
    try:
        import tkinter as tk
    except Exception as exc:
        raise SystemExit("Tkinter is required for local-agent-bridge-app: %s" % exc)
    append_runtime_log("desktop_app.log", "Desktop app started")
    root = tk.Tk()
    BridgeDesktopApp(root, protocol_url=protocol_url, start_hidden=start_hidden)
    root.mainloop()
