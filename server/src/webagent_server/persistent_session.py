# -*- coding: ascii -*-
"""Persistent Codex session manager using the app-server JSON-RPC protocol.

Instead of spawning a one-shot ``codex exec`` per request, this module keeps a
long-lived Codex process running in app-server mode.  Multiple turns reuse the
same thread so the agent retains full context across messages.

Enable via ``WEBAGENT_PERSISTENT_SESSIONS=1``.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_REQUEST_ID_COUNTER = 0
_REQUEST_ID_LOCK = threading.Lock()


def _next_request_id() -> int:
    global _REQUEST_ID_COUNTER
    with _REQUEST_ID_LOCK:
        _REQUEST_ID_COUNTER += 1
        return _REQUEST_ID_COUNTER


def _jsonrpc_request(method: str, params: Any, request_id: Optional[int] = None) -> str:
    if request_id is None:
        request_id = _next_request_id()
    msg = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    return json.dumps(msg, ensure_ascii=True) + "\n"


class PersistentCodexSession:
    """Wraps a long-lived Codex app-server process for multi-turn conversations."""

    def __init__(
        self,
        codex_cli_path: str,
        cwd: str,
        extra_args: Optional[List[str]] = None,
        hidden_kwargs: Optional[Dict[str, Any]] = None,
        idle_timeout: float = 600.0,
    ) -> None:
        self.codex_cli_path = codex_cli_path
        self.cwd = cwd
        self.extra_args = extra_args or []
        self.hidden_kwargs = hidden_kwargs or {}
        self.idle_timeout = idle_timeout

        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._thread_id: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._pending: Dict[int, threading.Event] = {}
        self._responses: Dict[int, Any] = {}
        self._notifications: List[Dict[str, Any]] = []
        self._notifications_lock = threading.Lock()
        self._last_activity = time.time()
        self._alive = False

    @property
    def is_alive(self) -> bool:
        with self._lock:
            if not self._alive or self._proc is None:
                return False
            return self._proc.poll() is None

    def _start_process(self) -> None:
        cmd = [self.codex_cli_path]
        cmd.extend(self.extra_args)
        cmd.extend(["--json"])
        self._proc = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self.hidden_kwargs,
        )
        self._alive = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self) -> None:
        """Read JSON-RPC responses and notifications from stdout."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for raw_line in proc.stdout:
            raw_line = str(raw_line or "").strip()
            if not raw_line:
                continue
            try:
                msg = json.loads(raw_line)
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            # JSON-RPC response (has "id")
            if "id" in msg and msg["id"] is not None:
                req_id = msg["id"]
                if isinstance(req_id, int) and req_id in self._pending:
                    self._responses[req_id] = msg
                    self._pending[req_id].set()
            else:
                # Notification (no id)
                with self._notifications_lock:
                    self._notifications.append(msg)
        with self._lock:
            self._alive = False

    def _send(self, data: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("Codex process not running")
        proc.stdin.write(data)
        proc.stdin.flush()

    def _request(self, method: str, params: Any, timeout: float = 30.0) -> Any:
        req_id = _next_request_id()
        event = threading.Event()
        self._pending[req_id] = event
        self._send(_jsonrpc_request(method, params, req_id))
        if not event.wait(timeout=timeout):
            self._pending.pop(req_id, None)
            raise TimeoutError("Codex app-server did not respond to %s within %ds" % (method, int(timeout)))
        self._pending.pop(req_id, None)
        resp = self._responses.pop(req_id, None)
        if isinstance(resp, dict) and "error" in resp:
            raise RuntimeError("Codex error: %s" % json.dumps(resp["error"]))
        return resp.get("result") if isinstance(resp, dict) else resp

    def drain_notifications(self) -> List[Dict[str, Any]]:
        with self._notifications_lock:
            items = list(self._notifications)
            self._notifications.clear()
        return items

    def ensure_started(self) -> None:
        with self._lock:
            if self._alive and self._proc is not None and self._proc.poll() is None:
                return
            self._start_process()

    def start_thread(self, instructions: Optional[str] = None, timeout: float = 30.0) -> str:
        self.ensure_started()
        params: Dict[str, Any] = {}
        if instructions:
            params["instructions"] = instructions
        result = self._request("thread/start", params, timeout=timeout)
        thread_id = ""
        if isinstance(result, dict):
            thread_id = str(result.get("threadId") or result.get("thread_id") or "")
        self._thread_id = thread_id
        self._last_activity = time.time()
        return thread_id

    def send_turn(self, message: str, timeout: float = 180.0) -> Iterator[Dict[str, Any]]:
        """Send a user message and yield streaming events until the turn completes."""
        self.ensure_started()
        if not self._thread_id:
            self.start_thread()
        # Clear old notifications
        self.drain_notifications()
        # Send turn/start
        params: Dict[str, Any] = {
            "threadId": self._thread_id,
            "message": message,
        }
        req_id = _next_request_id()
        event = threading.Event()
        self._pending[req_id] = event
        self._send(_jsonrpc_request("turn/start", params, req_id))
        self._last_activity = time.time()
        # Yield notifications until turn completes or we get the response
        deadline = time.time() + timeout if timeout > 0 else 0
        turn_done = False
        while not turn_done:
            if deadline and time.time() > deadline:
                self._pending.pop(req_id, None)
                yield {"_event": "error", "error": "Persistent session turn timed out after %ds" % int(timeout)}
                return
            # Check if the request got a response (turn accepted)
            if event.is_set():
                resp = self._responses.pop(req_id, None)
                self._pending.pop(req_id, None)
                if isinstance(resp, dict) and "error" in resp:
                    yield {"_event": "error", "error": "Turn start error: %s" % json.dumps(resp.get("error"))}
                    return
            # Drain and yield notifications
            notifications = self.drain_notifications()
            for notif in notifications:
                method = str(notif.get("method") or "").strip()
                notif_params = notif.get("params") if isinstance(notif.get("params"), dict) else {}
                # Map app-server notifications to exec-style events
                if method == "thread/turnCompleted":
                    turn_done = True
                    yield {"type": "turn.completed", **notif_params}
                    break
                elif method == "thread/turnFailed":
                    turn_done = True
                    yield {"_event": "error", "error": str(notif_params.get("error") or "turn failed")}
                    break
                elif method == "thread/itemStarted":
                    yield {"type": "item.started", "item": notif_params.get("item", {})}
                elif method == "thread/itemCompleted":
                    yield {"type": "item.completed", "item": notif_params.get("item", {})}
                elif method == "thread/itemUpdated":
                    yield {"type": "item.updated", "item": notif_params.get("item", {})}
                elif method == "thread/turnStarted":
                    yield {"type": "turn.started", **notif_params}
                else:
                    # Forward unknown notifications as-is
                    yield notif_params if notif_params else notif
            if not turn_done:
                time.sleep(0.05)
        self._last_activity = time.time()

    def interrupt(self) -> None:
        if not self._thread_id:
            return
        try:
            self._request("turn/interrupt", {"threadId": self._thread_id}, timeout=5.0)
        except Exception:
            pass

    def shutdown(self) -> None:
        with self._lock:
            self._alive = False
            proc = self._proc
            self._proc = None
            self._thread_id = None
        if proc is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    @property
    def last_activity(self) -> float:
        return self._last_activity

    @property
    def thread_id(self) -> Optional[str]:
        return self._thread_id


# ---------------------------------------------------------------------------
# Session pool: keyed by origin so each website gets its own persistent session
# ---------------------------------------------------------------------------

_SESSIONS_LOCK = threading.Lock()
_SESSIONS: Dict[str, PersistentCodexSession] = {}
_SESSION_IDLE_TIMEOUT = max(60, int(os.getenv("WEBAGENT_SESSION_IDLE_TIMEOUT", "600") or 600))


def get_or_create_session(
    origin: str,
    codex_cli_path: str,
    cwd: str,
    extra_args: Optional[List[str]] = None,
    hidden_kwargs: Optional[Dict[str, Any]] = None,
) -> PersistentCodexSession:
    key = origin or "_default"
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(key)
        if session is not None and session.is_alive:
            return session
        # Clean up dead session
        if session is not None:
            try:
                session.shutdown()
            except Exception:
                pass
        session = PersistentCodexSession(
            codex_cli_path=codex_cli_path,
            cwd=cwd,
            extra_args=extra_args,
            hidden_kwargs=hidden_kwargs,
            idle_timeout=float(_SESSION_IDLE_TIMEOUT),
        )
        _SESSIONS[key] = session
        return session


def close_session(origin: str) -> bool:
    key = origin or "_default"
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(key, None)
    if session is not None:
        session.shutdown()
        return True
    return False


def close_all_sessions() -> int:
    with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())
        _SESSIONS.clear()
    for session in sessions:
        try:
            session.shutdown()
        except Exception:
            pass
    return len(sessions)


def cleanup_idle_sessions() -> int:
    now = time.time()
    to_remove: List[str] = []
    with _SESSIONS_LOCK:
        for key, session in _SESSIONS.items():
            if now - session.last_activity > session.idle_timeout:
                to_remove.append(key)
        removed = []
        for key in to_remove:
            session = _SESSIONS.pop(key, None)
            if session is not None:
                removed.append(session)
    for session in removed:
        try:
            session.shutdown()
        except Exception:
            pass
    return len(removed)


def persistent_sessions_enabled() -> bool:
    return str(os.getenv("WEBAGENT_PERSISTENT_SESSIONS", "0") or "0").strip().lower() in ("1", "true", "yes", "on")
