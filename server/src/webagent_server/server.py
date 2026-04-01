# -*- coding: ascii -*-
from __future__ import annotations

import csv
import hashlib
import html as html_lib
import importlib.util
import json
import os
import re
import secrets
import signal
import shutil
import subprocess
import threading
import time
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from importlib import metadata as importlib_metadata
except Exception:  # pragma: no cover
    import importlib_metadata  # type: ignore

import requests
from flask import Flask, Response, jsonify, request

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = Path(__file__).resolve().with_name("docs")
DATA_DIR = Path(str(os.getenv("WEBAGENT_DATA_DIR", "") or "")).expanduser() if str(os.getenv("WEBAGENT_DATA_DIR", "") or "").strip() else (Path.home() / ".local-agent-bridge")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PLUGIN_DIR = DATA_DIR / "plugins"
PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
APPROVED_ORIGINS_FILE = DATA_DIR / "approved_origins.json"
APPROVAL_LOG_DIR = DATA_DIR / "approval_logs"
APPROVAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

_ACTIVE_CODEX_LOCK = threading.Lock()
_ACTIVE_CODEX_PROC = None
_ACTIVE_CLAUDE_LOCK = threading.Lock()
_ACTIVE_CLAUDE_PROC = None
_APPROVAL_TOKENS_LOCK = threading.Lock()
_APPROVAL_TOKENS: Dict[str, Dict[str, Any]] = {}
_BRIDGE_TOOLS_LOCK = threading.Lock()
_BRIDGE_TOOLS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

_PROMPT_TOKEN_BUDGET = max(2000, int(os.getenv("CODEX_PROMPT_TOKEN_BUDGET", "12000") or 12000))
_SUMMARY_MAX_LINES = max(4, int(os.getenv("CODEX_SUMMARY_MAX_LINES", "20") or 20))
_VERIFY_FINAL = str(os.getenv("CODEX_VERIFY_FINAL", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
_DOC_CHAR_BUDGET = max(1000, int(os.getenv("CODEX_DOC_CHAR_BUDGET", "9000") or 9000))
_APPROVAL_TOKEN_TTL_SECONDS = max(60, int(os.getenv("WEBAGENT_APPROVAL_TOKEN_TTL", "900") or 900))


def _hidden_subprocess_kwargs() -> Dict[str, Any]:
    if os.name != "nt":
        return {}
    kwargs: Dict[str, Any] = {}
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    try:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    except Exception:
        pass
    return kwargs


def _kill_process_tree(proc: Optional[subprocess.Popen]) -> bool:
    if proc is None:
        return False
    try:
        if proc.poll() is not None:
            return False
    except Exception:
        return False
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_subprocess_kwargs(),
            )
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        return True
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5)
            return True
        except Exception:
            return False


def _plugin_context() -> Dict[str, Any]:
    return {
        "data_dir": DATA_DIR,
        "plugin_dir": PLUGIN_DIR,
        "downloads_dir": Path.home() / "Downloads",
    }


def _normalize_tool_name(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", raw) else ""


def _tool_manifest_view(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(tool.get("name") or ""),
        "description": str(tool.get("description") or "").strip(),
        "args_schema": tool.get("args_schema") if isinstance(tool.get("args_schema"), dict) else {"type": "object"},
        "permissions": list(tool.get("permissions") or []),
        "source": str(tool.get("source") or "").strip(),
    }


def _load_tools_from_provider(provider: Any, source: str) -> List[Dict[str, Any]]:
    tools = provider(_plugin_context()) if callable(provider) else provider
    loaded: List[Dict[str, Any]] = []
    for item in list(tools or []):
        if not isinstance(item, dict):
            continue
        name = _normalize_tool_name(item.get("name"))
        handler = item.get("handler")
        if not name or not callable(handler):
            continue
        loaded.append({
            "name": name,
            "description": str(item.get("description") or "").strip(),
            "args_schema": item.get("args_schema") if isinstance(item.get("args_schema"), dict) else {"type": "object"},
            "permissions": [str(v).strip() for v in list(item.get("permissions") or []) if str(v).strip()],
            "handler": handler,
            "source": source,
        })
    return loaded


def _load_tools_from_module(module: Any, source: str) -> List[Dict[str, Any]]:
    if hasattr(module, "register_tools") and callable(module.register_tools):  # type: ignore[attr-defined]
        return _load_tools_from_provider(module.register_tools, source)  # type: ignore[attr-defined]
    if hasattr(module, "TOOLS"):
        return _load_tools_from_provider(getattr(module, "TOOLS"), source)
    return []


def _discover_bridge_tools() -> Dict[str, Dict[str, Any]]:
    discovered: Dict[str, Dict[str, Any]] = {}

    def add_tools(items: List[Dict[str, Any]]) -> None:
        for tool in items:
            discovered[str(tool["name"])] = tool

    try:
        from webagent_server.plugins import save_text_file

        add_tools(_load_tools_from_module(save_text_file, "builtin:webagent_server.plugins.save_text_file"))
    except Exception:
        pass

    try:
        entry_points = importlib_metadata.entry_points()
        selected = entry_points.select(group="webagent.plugins") if hasattr(entry_points, "select") else entry_points.get("webagent.plugins", [])
        for entry_point in selected:
            try:
                loaded = entry_point.load()
                source = "package:" + str(getattr(entry_point, "name", "") or "plugin")
                if hasattr(loaded, "register_tools") or hasattr(loaded, "TOOLS"):
                    add_tools(_load_tools_from_module(loaded, source))
                else:
                    add_tools(_load_tools_from_provider(loaded, source))
            except Exception:
                continue
    except Exception:
        pass

    try:
        for path in sorted(PLUGIN_DIR.glob("*.py")):
            try:
                spec = importlib.util.spec_from_file_location("webagent_plugin_" + path.stem, str(path))
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                add_tools(_load_tools_from_module(module, "file:" + str(path)))
            except Exception:
                continue
    except Exception:
        pass
    return discovered


def _bridge_tools() -> Dict[str, Dict[str, Any]]:
    global _BRIDGE_TOOLS_CACHE
    with _BRIDGE_TOOLS_LOCK:
        if _BRIDGE_TOOLS_CACHE is None:
            _BRIDGE_TOOLS_CACHE = _discover_bridge_tools()
        return dict(_BRIDGE_TOOLS_CACHE)


def _bridge_tool_manifests() -> List[Dict[str, Any]]:
    return [_tool_manifest_view(tool) for _, tool in sorted(_bridge_tools().items(), key=lambda item: item[0].lower())]


def _bridge_tool_prompt_lines() -> List[str]:
    tools = _bridge_tool_manifests()
    if not tools:
        return []
    lines = [
        "Installed bridge extension tools are also available. To call one, set action.type to the exact tool name and put the tool inputs inside args.",
        "Installed bridge tools:",
    ]
    for tool in tools[:24]:
        args_schema = tool.get("args_schema") if isinstance(tool.get("args_schema"), dict) else {}
        props = args_schema.get("properties") if isinstance(args_schema.get("properties"), dict) else {}
        arg_names = ", ".join(list(props.keys())[:8])
        detail = "- %s: %s" % (tool["name"], _clip_text(tool.get("description") or "", 180))
        if arg_names:
            detail += " | args: " + arg_names
        if tool.get("permissions"):
            detail += " | permissions: " + ", ".join(tool["permissions"][:6])
        lines.append(detail)
    return lines


def _execute_bridge_tool(name: str, args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    tools = _bridge_tools()
    tool = tools.get(str(name or "").strip())
    if not tool:
        raise ValueError("unknown tool: " + str(name or ""))
    payload = dict(args or {}) if isinstance(args, dict) else {}
    result = tool["handler"](payload, _plugin_context())
    if isinstance(result, dict):
        output = dict(result)
    else:
        output = {"ok": True, "result": result}
    output.setdefault("ok", True)
    output.setdefault("tool", tool["name"])
    output.setdefault("source", tool["source"])
    return output


def _clip_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def _summarize_progress_text(value: Any) -> str:
    return _clip_text(re.sub(r"\s+", " ", str(value or "")).strip(), 180)


def _summarize_progress_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(text)
        if parsed.scheme and parsed.netloc:
            return _clip_text((parsed.netloc + parsed.path).strip(), 140)
    except Exception:
        pass
    return _clip_text(text, 140)


def _describe_native_progress_event(event: Any) -> Optional[str]:
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("type") or "").strip()
    item = event.get("item") if isinstance(event.get("item"), dict) else {}
    item_type = str(item.get("type") or "").strip()
    if event_type in ("thinking", "heartbeat"):
        return _summarize_progress_text(event.get("text") or "Thinking...")
    if event_type == "thread.started":
        return "Session started"
    if event_type == "turn.started":
        return "Thinking..."
    if event_type == "turn.completed":
        return "Turn complete"
    if event_type == "item.started":
        if item_type == "web_search":
            query = _summarize_progress_text(item.get("query") or ((item.get("action") or {}).get("query") if isinstance(item.get("action"), dict) else ""))
            return f"Searching web: {query}" if query else "Searching web..."
        if item_type == "web_fetch":
            url = _summarize_progress_url(item.get("url") or item.get("href"))
            return f"Fetching page: {url}" if url else "Fetching page..."
        if item_type == "command_execution":
            command = _summarize_progress_text(item.get("command") or item.get("cmd") or item.get("executable") or item.get("program"))
            return f"Running command: {command}" if command else "Running command..."
        if item_type == "mcp_tool_call":
            label = _clip_text(item.get("tool") or item.get("server") or "MCP tool", 100)
            return f"Calling {label}..."
        if item_type == "agent_message":
            return _summarize_progress_text(item.get("text") or item.get("content") or "Agent update...")
    if event_type == "item.completed":
        if item_type == "web_search":
            query = _summarize_progress_text(item.get("query") or ((item.get("action") or {}).get("query") if isinstance(item.get("action"), dict) else ""))
            return f"Searched web: {query}" if query else "Web search done"
        if item_type == "web_fetch":
            url = _summarize_progress_url(item.get("url") or item.get("href"))
            return f"Fetched page: {url}" if url else "Page fetch done"
        if item_type == "command_execution":
            command = _summarize_progress_text(item.get("command") or item.get("cmd") or item.get("executable") or item.get("program"))
            exit_code = item.get("exit_code")
            if exit_code in (None, 0):
                return f"Command done: {command}" if command else "Command done"
            return f"Command failed ({exit_code}): {command}" if command else f"Command failed (exit {exit_code})"
        if item_type == "mcp_tool_call":
            label = _clip_text(item.get("tool") or item.get("server") or "tool", 100)
            return f"Tool call failed: {label}" if str(item.get("status") or "") == "failed" else f"Tool call done: {label}"
        if item_type == "agent_message":
            return _summarize_progress_text(item.get("text") or item.get("content"))
    if event.get("text"):
        return _summarize_progress_text(event.get("text"))
    return None


def _strip_html_text(raw_html: Any) -> str:
    text = str(raw_html or "")
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript\b.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_object(text: Any) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[idx:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _estimate_tokens_text(value: Any) -> int:
    return max(1, (len(str(value or "")) + 3) // 4)


def _compact_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    rendered = []
    for idx, msg in enumerate(list(messages or []), start=1):
        role = str((msg or {}).get("role") or "user").upper()
        text = str((msg or {}).get("content") or "").strip()
        rendered.append({"idx": idx, "recent": f"{idx}. {role}: {_clip_text(text, 4000)}", "summary": f"{idx}. {role}: {_clip_text(text, 180)}"})
    recent_lines: List[str] = []
    recent_tokens = 0
    recent_budget = max(800, int(_PROMPT_TOKEN_BUDGET * 0.6))
    for item in reversed(rendered):
        line_tokens = _estimate_tokens_text(item["recent"])
        if recent_lines and recent_tokens + line_tokens > recent_budget:
            break
        recent_lines.append(item["recent"])
        recent_tokens += line_tokens
    recent_lines.reverse()
    recent_start_idx = rendered[-len(recent_lines)]["idx"] if recent_lines else len(rendered) + 1
    older_items = [item for item in rendered if item["idx"] < recent_start_idx]
    summary_lines = [item["summary"] for item in older_items[-_SUMMARY_MAX_LINES:]]
    return {"older_summary": summary_lines, "recent_messages": recent_lines}


def _compact_app_context(app_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(app_context, dict):
        return {}
    compact = {
        "title": _clip_text(app_context.get("title"), 160),
        "path": _clip_text(app_context.get("path"), 120),
        "url": _clip_text(app_context.get("url"), 240),
        "visible_text_sample": _clip_text(app_context.get("visible_text_sample"), 1200),
        "agent_backend": _clip_text(app_context.get("agent_backend"), 24),
    }
    compact["hosted_doc_links"] = [
        {
            "href": _clip_text(item.get("href") or item.get("url"), 280),
            "title": _clip_text(item.get("title"), 160),
            "source": _clip_text(item.get("source"), 24),
        }
        for item in list(app_context.get("hosted_doc_links") or [])[:12]
        if isinstance(item, dict)
    ]
    compact["hosted_doc_files"] = [
        {
            "href": _clip_text(item.get("href") or item.get("url"), 280),
            "title": _clip_text(item.get("title"), 160),
            "source": _clip_text(item.get("source"), 24),
            "mime_type": _clip_text(item.get("mime_type"), 80),
            "char_count": int(item.get("char_count") or len(str(item.get("content") or ""))),
            "content": _clip_text(item.get("content"), 1200),
        }
        for item in list(app_context.get("hosted_doc_files") or [])[:8]
        if isinstance(item, dict)
    ]
    if isinstance(app_context.get("host_context"), dict):
        compact["host_context"] = {str(k)[:64]: _clip_text(v, 300) for k, v in list(app_context.get("host_context").items())[:16]}
    run_log_entries = app_context.get("run_log_tail") or app_context.get("run_log")
    if isinstance(run_log_entries, list):
        compact["run_log_tail"] = [
            {
                "ts": _clip_text(item.get("ts"), 40),
                "kind": _clip_text(item.get("kind"), 32),
                "detail": _clip_text(item.get("detail"), 220),
            }
            for item in run_log_entries[-40:]
            if isinstance(item, dict) and (item.get("detail") or item.get("kind"))
        ]
    return compact


def _run_log_section(app_context: Optional[Dict[str, Any]]) -> str:
    if not isinstance(app_context, dict):
        return ""
    run_log_entries = app_context.get("run_log_tail") or app_context.get("run_log")
    if not isinstance(run_log_entries, list):
        return ""
    lines: List[str] = []
    for item in run_log_entries[-40:]:
        if not isinstance(item, dict):
            continue
        detail = _clip_text(item.get("detail"), 220)
        kind = _clip_text(item.get("kind"), 32)
        ts = _clip_text(item.get("ts"), 40)
        if not detail and not kind:
            continue
        prefix = f"[{ts}] " if ts else ""
        if kind:
            prefix += kind + " - "
        lines.append("- " + prefix + (detail or "(no detail)"))
    return "\n".join(lines).strip()


def _hosted_docs_section(app_context: Optional[Dict[str, Any]]) -> str:
    if not isinstance(app_context, dict):
        return ""
    lines: List[str] = []
    host_context = app_context.get("host_context")
    if isinstance(host_context, dict) and host_context:
        lines.append("Host context:")
        for key, value in list(host_context.items())[:16]:
            lines.append(f"- {str(key)[:64]}: {_clip_text(value, 300)}")
    for item in list(app_context.get("hosted_doc_links") or [])[:12]:
        if not isinstance(item, dict):
            continue
        href = _clip_text(item.get("href") or item.get("url"), 280)
        if href:
            lines.append(f"- {_clip_text(item.get('title') or href, 160)}: {href}")
    for item in list(app_context.get("hosted_doc_files") or [])[:6]:
        if not isinstance(item, dict):
            continue
        href = _clip_text(item.get("href") or item.get("url"), 280)
        title = _clip_text(item.get("title") or href or "Host file", 160)
        mime_type = _clip_text(item.get("mime_type"), 80)
        content = _clip_text(item.get("content"), 1800)
        if not content and not href:
            continue
        descriptor = title
        if mime_type:
            descriptor += f" [{mime_type}]"
        if href:
            descriptor += f" ({href})"
        lines.append(f"- Embedded host file: {descriptor}")
        if content:
            lines.append("```")
            lines.append(content)
            lines.append("```")
    return "\n".join(lines).strip()


def _doc_paths() -> List[str]:
    raw = str(os.getenv("CODEX_AGENT_DOC_PATHS", "") or "").strip()
    if raw:
        return [item.strip() for item in raw.split(os.pathsep) if item.strip()]
    return [str(DOCS_DIR / "CODEX_AGENT_CONTEXT_SUMMARY.md"), str(DOCS_DIR / "CODEX_AGENT_CONTEXT.md")]


@lru_cache(maxsize=1)
def _context_docs() -> Dict[str, Any]:
    sections: List[str] = []
    loaded_paths: List[str] = []
    for path in _doc_paths():
        if not os.path.exists(path):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if not text:
            continue
        remaining = _DOC_CHAR_BUDGET - sum(len(section) for section in sections)
        if remaining <= 0:
            break
        sections.append(f"[{os.path.basename(path)}]\n{_clip_text(text, min(remaining, 6000))}")
        loaded_paths.append(path)
    combined = "\n\n".join(sections).strip()
    return {"text": combined, "paths": loaded_paths, "digest": hashlib.sha1(combined.encode("utf-8")).hexdigest()[:12] if combined else ""}


def _app_instructions_text() -> str:
    path = str(os.getenv("CODEX_AGENT_INSTRUCTIONS_PATH", "") or "").strip()
    if not path or not os.path.exists(path):
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _hybrid_agent_tools_enabled() -> bool:
    return str(os.getenv("WEBAGENT_HYBRID_AGENT_TOOLS", "1") or "1").strip().lower() not in ("0", "false", "no", "off")


def _bridge_web_tools_enabled() -> bool:
    default = "0" if _hybrid_agent_tools_enabled() else "1"
    return str(os.getenv("WEBAGENT_ALLOW_BRIDGE_WEB_TOOLS", default) or default).strip().lower() not in ("0", "false", "no", "off")


def _website_action_types() -> List[str]:
    actions = [
        "clickSelector",
        "setInputValue",
        "navigateStock",
        "queryDb",
        "fetchDbTables",
        "fetchDbStatus",
        "exportQueryToCsv",
        "getPageState",
        "getVisibleProducts",
        "getDomTree",
        "fetchDomHtml",
        "renderAgentHtml",
        "appendAgentHtml",
    ]
    if _bridge_web_tools_enabled():
        actions.extend(["webSearch", "fetchWebPage"])
    return actions


def _response_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "reason": {"type": "string"},
                        "args": {"type": ["object", "null"], "additionalProperties": True},
                        "selector": {"type": ["string", "null"]},
                        "value": {"type": ["string", "null"]},
                        "symbol": {"type": ["string", "null"]},
                        "sql": {"type": ["string", "null"]},
                        "path": {"type": ["string", "null"]},
                        "url": {"type": ["string", "null"]},
                        "query": {"type": ["string", "null"]},
                        "limit": {"type": ["integer", "null"]},
                        "offset": {"type": ["integer", "null"]},
                    },
                    "required": ["type", "reason", "args", "selector", "value", "symbol", "sql", "path", "url", "query", "limit", "offset"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["message", "actions"],
        "additionalProperties": False,
    }


def _write_json_schema(filename: str, schema: Dict[str, Any]) -> str:
    path = DATA_DIR / filename
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return str(path)


def _normalize_agent_action(action: Any) -> Dict[str, Any]:
    base = dict(action or {}) if isinstance(action, dict) else {}
    args = base.get("args") if isinstance(base.get("args"), dict) else {}
    def pick(key: str, fallback_key: Optional[str] = None):
        val = base.get(key)
        if val is not None:
            return val
        return args.get(fallback_key or key)
    normalized = {
        "type": str(base.get("type") or "").strip(),
        "reason": str(base.get("reason") or "").strip(),
        "args": dict(args) if args else None,
        "selector": pick("selector"),
        "value": pick("value", "html"),
        "symbol": pick("symbol"),
        "sql": pick("sql"),
        "path": pick("path"),
        "url": pick("url"),
        "query": pick("query"),
        "limit": pick("limit"),
        "offset": pick("offset"),
    }
    for key in ("selector", "value", "symbol", "sql", "path", "url", "query"):
        if normalized[key] is not None and not isinstance(normalized[key], str):
            normalized[key] = str(normalized[key])
    for key in ("limit", "offset"):
        try:
            normalized[key] = None if normalized[key] in (None, "") else int(normalized[key])
        except Exception:
            normalized[key] = None
    return normalized


def _normalize_response(parsed: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    return {
        "message": str((parsed or {}).get("message") or "").strip(),
        "actions": [_normalize_agent_action(item) for item in list((parsed or {}).get("actions") or []) if isinstance(item, dict)],
        "model": model_name,
    }


def _clean_codex_cli_error(raw: Any) -> str:
    text = str(raw or "").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    filtered = [line for line in lines if not line.lower().startswith(("openai codex v", "workdir:", "model:", "provider:", "approval:", "sandbox:", "reasoning effort:", "reasoning summaries:", "session id:"))]
    return _clip_text("\n".join(filtered[:6]).strip() or "Codex request failed.", 500)


def _resolve_cli(env_key: str, fallback: str) -> str:
    override = str(os.getenv(env_key, "") or "").strip()
    if override:
        return override
    found = shutil.which(fallback)
    return found or fallback


def _codex_cli_path() -> str:
    return _resolve_cli("CODEX_CLI_PATH", "codex.cmd" if os.name == "nt" else "codex")


def _claude_cli_path() -> str:
    return _resolve_cli("CLAUDE_CODE_EXE", "claude")


def _codex_extra_cli_args() -> List[str]:
    args: List[str] = []
    profile = str(os.getenv("CODEX_CLI_PROFILE", "") or "").strip()
    if profile:
        args.extend(["--profile", profile])
    return args


def _build_prompt(messages: List[Dict[str, Any]], app_context: Optional[Dict[str, Any]]) -> str:
    website_actions = ", ".join(_website_action_types())
    parts = [
        "You are an embedded website agent backend.",
        "Inspect the provided app context and conversation history.",
        "Website action types available to you: " + website_actions + ".",
        "Use website action objects only for host-specific UI operations, Agent Workspace rendering, and bridge-backed helpers.",
        "If native agent tools are available, prefer them for general web research, reading, reasoning, and other non-website-specific work.",
        "Host-provided docs may include inline same-origin file contents from the page; treat those embedded files as authoritative website reference material.",
        "Do not use local shell commands or local filesystem searches to discover website content, selectors, products, or page state unless the user explicitly asks about local repo files.",
        "Assume a normal end user does not have a local checkout of the website. For host evidence, rely on app context, host-provided inline docs, website actions, and same-origin web content instead of local workspace files.",
        "For website tasks, command execution for local file or shell inspection is forbidden unless the user explicitly asks about local project files.",
        "Prefer structured website reads like getVisibleProducts and getPageState before using raw fetchDomHtml on dynamic catalog pages.",
        "Use getDomTree as a compact live semantic snapshot of the page or a specific container when you need to understand layout, controls, or visible sections without pulling full HTML.",
        "For getDomTree actions: selector is the root selector (or null for body), offset is max depth, limit is max nodes, and value is the per-node text limit.",
        "Do not run native shell commands like rg, grep, pwsh, bash, dir, or Get-ChildItem just to inspect the current website when website actions or inline host docs can answer it.",
        "If you are about to inspect local files to answer a website question, stop and use website actions or host-provided docs instead.",
        "When getVisibleProducts returns a visible catalog count and structured item list, treat it as complete storefront evidence for the current page state unless the page changes.",
        "Keep web research tight: usually no more than 6 targeted searches per turn, and avoid repeating near-duplicate searches for the same product once you have an official source plus one strong review/comparison source.",
        "Do not emit webSearch or fetchWebPage actions unless bridge web tools are explicitly available and native agent tools are unavailable or clearly insufficient.",
        "Return strict JSON that matches the provided schema.",
        "For every action object, include args, selector, value, symbol, sql, path, url, query, limit, and offset. Use null when not applicable.",
        "For installed bridge extension tools, put tool inputs inside args and leave unrelated flat fields null.",
        "Use renderAgentHtml for live workspace updates when the host exposes an Agent Workspace.",
    ]
    tool_prompt_lines = _bridge_tool_prompt_lines()
    if tool_prompt_lines:
        parts.append("\n".join(tool_prompt_lines))
    extra = _app_instructions_text()
    if extra:
        parts.append("App-specific instructions:\n" + extra)
    docs = _context_docs()
    hosted_docs = _hosted_docs_section(app_context)
    compact_context = _compact_app_context(app_context)
    compact_messages = _compact_messages(messages)
    if docs["text"]:
        parts.append("Project context docs:\n" + docs["text"])
    if hosted_docs:
        parts.append("Host-provided docs and context:\n" + hosted_docs)
    if compact_context:
        parts.append("App context JSON:\n" + json.dumps(compact_context, ensure_ascii=True))
    if compact_messages["older_summary"]:
        parts.append("Older conversation summary:\n" + "\n".join(compact_messages["older_summary"]))
    parts.append("Recent conversation:\n" + "\n".join(compact_messages["recent_messages"]))
    return "\n\n".join(parts)


def _codex_exec_structured(prompt: str, schema_filename: str, timeout: int = 180) -> Dict[str, Any]:
    schema_path = _write_json_schema(schema_filename, _response_schema())
    cmd = [_codex_cli_path()]
    if _hybrid_agent_tools_enabled():
        cmd.append("--search")
    cmd.extend(["exec", "--skip-git-repo-check", "--sandbox", "read-only"])
    cmd.extend(_codex_extra_cli_args())
    cmd.extend(["--output-schema", schema_path, "-"])
    global _ACTIVE_CODEX_PROC
    proc = subprocess.Popen(
        cmd,
        cwd=str(PACKAGE_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_hidden_subprocess_kwargs(),
    )
    with _ACTIVE_CODEX_LOCK:
        _ACTIVE_CODEX_PROC = proc
    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        raise RuntimeError("Codex CLI timed out after %d seconds" % timeout)
    finally:
        with _ACTIVE_CODEX_LOCK:
            if _ACTIVE_CODEX_PROC is proc:
                _ACTIVE_CODEX_PROC = None
    if proc.returncode != 0:
        raise RuntimeError(_clean_codex_cli_error(stderr or stdout or "codex failed"))
    parsed = _extract_json_object(stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("Codex response was not a JSON object")
    return _normalize_response(parsed, "codex-cli-local")


def _codex_exec_streaming(prompt: str, schema_filename: str, timeout: int = 180):
    schema_path = _write_json_schema(schema_filename, _response_schema())
    cmd = [_codex_cli_path()]
    if _hybrid_agent_tools_enabled():
        cmd.append("--search")
    cmd.extend(["exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only"])
    cmd.extend(_codex_extra_cli_args())
    cmd.extend(["--output-schema", schema_path, "-"])
    global _ACTIVE_CODEX_PROC
    proc = subprocess.Popen(
        cmd,
        cwd=str(PACKAGE_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_hidden_subprocess_kwargs(),
    )
    with _ACTIVE_CODEX_LOCK:
        _ACTIVE_CODEX_PROC = proc

    def _feed() -> None:
        try:
            if proc.stdin is not None:
                proc.stdin.write(prompt)
                proc.stdin.close()
        except Exception:
            pass

    threading.Thread(target=_feed, daemon=True).start()
    deadline = time.time() + timeout if timeout else 0
    collected_items: List[Dict[str, Any]] = []
    try:
        for raw_line in proc.stdout or []:
            if deadline and time.time() > deadline:
                _kill_process_tree(proc)
                yield {"_event": "error", "error": "Codex CLI timed out after %d seconds" % timeout}
                return
            raw_line = str(raw_line or "").strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except Exception:
                continue
            if isinstance(event, dict) and event.get("type") == "item.completed":
                collected_items.append(event.get("item") or {})
            yield event
        proc.wait(timeout=10)
    except Exception as exc:
        _kill_process_tree(proc)
        yield {"_event": "error", "error": str(exc)}
        return
    finally:
        with _ACTIVE_CODEX_LOCK:
            if _ACTIVE_CODEX_PROC is proc:
                _ACTIVE_CODEX_PROC = None
    if proc.returncode != 0:
        stderr_text = ""
        try:
            stderr_text = proc.stderr.read() if proc.stderr is not None else ""
        except Exception:
            pass
        yield {"_event": "error", "error": _clean_codex_cli_error(stderr_text or "codex failed")}
        return
    message_parts = []
    for item in collected_items:
        if isinstance(item, dict) and item.get("type") == "agent_message":
            message_parts.append(str(item.get("text") or ""))
    final_text = "\n".join(message_parts).strip()
    parsed = _extract_json_object(final_text)
    if isinstance(parsed, dict):
        result = _normalize_response(parsed, "codex-cli-local")
    elif final_text:
        result = _normalize_response({"message": final_text, "actions": []}, "codex-cli-local")
    else:
        yield {"_event": "error", "error": "Codex returned no agent message"}
        return
    yield {"_event": "done", "result": result}


def _verify_final_response(candidate: Dict[str, Any], messages: List[Dict[str, Any]], app_context: Optional[Dict[str, Any]], native_activity: Optional[List[str]] = None) -> Dict[str, Any]:
    if not _VERIFY_FINAL or candidate.get("actions"):
        return candidate
    docs = _context_docs()
    compact_context = _compact_app_context(app_context)
    compact_messages = _compact_messages(messages)
    run_log_section = _run_log_section(app_context)
    prompt_parts = [
        "Review the proposed final answer for false completion or unsupported claims.",
        "Return strict JSON that matches the provided schema.",
        "Treat native agent activity and run-log evidence as valid evidence of what the agent actually did, even if no explicit bridge webSearch or fetchWebPage actions were emitted.",
        "Do not reject web-research claims solely because the resolved website actions only include renderAgentHtml or other host-specific actions if native web_search or web_fetch activity is documented below.",
    ]
    if docs["text"]:
        prompt_parts.append("Project context docs:\n" + docs["text"])
    if compact_context:
        prompt_parts.append("App context JSON:\n" + json.dumps(compact_context, ensure_ascii=True))
    if run_log_section:
        prompt_parts.append("Recent run log:\n" + run_log_section)
    if native_activity:
        prompt_parts.append("Current turn native activity:\n" + "\n".join("- " + _clip_text(item, 220) for item in native_activity[-30:] if str(item or "").strip()))
    if compact_messages["older_summary"]:
        prompt_parts.append("Older conversation summary:\n" + "\n".join(compact_messages["older_summary"]))
    prompt_parts.append("Recent conversation:\n" + "\n".join(compact_messages["recent_messages"]))
    prompt_parts.append("Proposed final response JSON:\n" + json.dumps(candidate, ensure_ascii=True))
    try:
        verified = _codex_exec_structured("\n\n".join(prompt_parts), "codex_verify_schema.json", timeout=120)
    except Exception:
        return candidate
    return verified if isinstance(verified, dict) else candidate


def _claude_cli_request(messages: List[Dict[str, Any]], app_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    website_actions = ", ".join(_website_action_types())
    docs = _context_docs()
    hosted_docs = _hosted_docs_section(app_context)
    prompt_parts = [
        "You are Claude Code embedded inside a website assistant backend.",
        "Website action types available to you: " + website_actions + ".",
        "Use website action objects only for host-specific UI operations, Agent Workspace rendering, and bridge-backed helpers.",
        "If native Claude tools are available in this session, prefer them for general research and reasoning before falling back to website actions.",
        "Host-provided docs may include inline same-origin file contents from the page; treat those embedded files as authoritative website reference material.",
        "Do not use local shell commands or local filesystem searches to discover website content, selectors, products, or page state unless the user explicitly asks about local repo files.",
        "Assume a normal end user does not have a local checkout of the website. For host evidence, rely on app context, host-provided inline docs, website actions, and same-origin web content instead of local workspace files.",
        "For website tasks, command execution for local file or shell inspection is forbidden unless the user explicitly asks about local project files.",
        "Prefer structured website reads like getVisibleProducts and getPageState before using raw fetchDomHtml on dynamic pages.",
        "Use getDomTree as a compact live semantic snapshot when you need to inspect page structure or a specific container without pulling full HTML.",
        "For getDomTree actions: selector is the root selector (or null for body), offset is max depth, limit is max nodes, and value is the per-node text limit.",
        "Do not run native shell commands like rg, grep, pwsh, bash, dir, or Get-ChildItem just to inspect the current website when website actions or inline host docs can answer it.",
        "If you are about to inspect local files to answer a website question, stop and use website actions or host-provided docs instead.",
        "When getVisibleProducts returns a visible catalog count and structured item list, treat it as complete storefront evidence for the current page state unless the page changes.",
        "Keep web research tight: usually no more than 6 targeted searches per turn, and avoid repeating near-duplicate searches for the same product once you have an official source plus one strong review/comparison source.",
        "Do not emit webSearch or fetchWebPage actions unless bridge web tools are explicitly available and native tools are unavailable or clearly insufficient.",
        "Return strict JSON only with keys: message, actions.",
        "Each action must include keys: type, reason, args, selector, value, symbol, sql, path, url, query, limit, offset.",
        "For installed bridge extension tools, put tool inputs inside args and leave unrelated flat fields null.",
        "Use null for any action fields that do not apply.",
    ]
    tool_prompt_lines = _bridge_tool_prompt_lines()
    if tool_prompt_lines:
        prompt_parts.append("\n".join(tool_prompt_lines))
    if docs["text"]:
        prompt_parts.append("Project context docs:\n" + docs["text"])
    if hosted_docs:
        prompt_parts.append("Host-provided docs and context:\n" + hosted_docs)
    if app_context:
        prompt_parts.append("App context JSON:\n" + json.dumps(app_context, ensure_ascii=True)[:50000])
    prompt_parts.append("Conversation:")
    for msg in messages or []:
        role = str((msg or {}).get("role") or "user").upper()
        prompt_parts.append(role + ": " + str((msg or {}).get("content") or ""))
    global _ACTIVE_CLAUDE_PROC
    proc = subprocess.Popen(
        [_claude_cli_path(), "-p", "--output-format", "text", "--permission-mode", "default"],
        cwd=str(PACKAGE_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_hidden_subprocess_kwargs(),
    )
    with _ACTIVE_CLAUDE_LOCK:
        _ACTIVE_CLAUDE_PROC = proc
    try:
        stdout, stderr = proc.communicate(input="\n\n".join(prompt_parts), timeout=120)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        raise RuntimeError("Claude CLI timed out after 120 seconds")
    finally:
        with _ACTIVE_CLAUDE_LOCK:
            if _ACTIVE_CLAUDE_PROC is proc:
                _ACTIVE_CLAUDE_PROC = None
    if proc.returncode != 0:
        raise RuntimeError(_clip_text(stderr or stdout or "claude failed", 1000))
    parsed = _extract_json_object(stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("Claude response was not a JSON object")
    return _normalize_response(parsed, "claude-code-local")


def _sql_is_read_only(sql: str) -> bool:
    s = str(sql or "").strip()
    if not s:
        return False
    lowered = s.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    if ";" in lowered.rstrip(";"):
        return False
    padded = " " + lowered.replace("\n", " ").replace("\r", " ") + " "
    blocked = [" insert ", " update ", " delete ", " drop ", " alter ", " truncate ", " create ", " merge ", " exec ", " execute "]
    return not any(token in padded for token in blocked)


def _db_connect():
    conn_str = str(os.getenv("SQL_CONN_STR", "") or "").strip()
    if not conn_str:
        raise RuntimeError("SQL_CONN_STR is not configured")
    try:
        import pyodbc  # type: ignore
    except Exception as exc:
        raise RuntimeError("pyodbc is not installed") from exc
    return pyodbc.connect(conn_str)


def _db_helper_run_query(sql: str, limit: Optional[int] = None) -> Dict[str, Any]:
    if not _sql_is_read_only(sql):
        raise ValueError("only read-only SELECT/WITH queries are allowed")
    cnx = _db_connect()
    try:
        cur = cnx.cursor()
        cur.execute(sql)
        columns = [str(c[0]) for c in (cur.description or [])]
        rows = []
        max_rows = None if limit in (None, "", 0) else max(1, int(limit))
        truncated = False
        for idx, row in enumerate(cur.fetchall()):
            if max_rows is not None and idx >= max_rows:
                truncated = True
                break
            rec = {}
            for col_idx, col_name in enumerate(columns):
                val = row[col_idx]
                rec[col_name] = val.isoformat() if isinstance(val, (datetime, date)) else val
            rows.append(rec)
        return {"columns": columns, "rows": rows, "row_count": len(rows), "limit_used": max_rows, "truncated": truncated}
    finally:
        try:
            cnx.close()
        except Exception:
            pass


def _resolve_export_path(path_value: Any) -> str:
    raw = str(path_value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("export path required")
    candidate = raw if raw.lower().endswith(".csv") else (raw + ".csv")
    full_path = (DATA_DIR / candidate).resolve()
    if DATA_DIR.resolve() not in full_path.parents and full_path != DATA_DIR.resolve():
        raise ValueError("export path must stay within the data folder")
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return str(full_path)


def _db_helper_export_csv(sql: str, path_value: Any) -> Dict[str, Any]:
    result = _db_helper_run_query(sql, limit=None)
    full_path = _resolve_export_path(path_value)
    columns = list(result.get("columns") or [])
    rows = list(result.get("rows") or [])
    with open(full_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns or [])
        if columns:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})
    return {"ok": True, "saved_path": str(Path(full_path).relative_to(PACKAGE_ROOT)).replace("\\", "/"), "absolute_path": full_path, "row_count": len(rows), "columns": columns}


def _web_search(query: str, limit: Optional[int] = None) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        raise ValueError("search query required")
    resp = requests.get("https://www.bing.com/search", params={"q": q}, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    matches = re.findall(r'(?is)<li[^>]+class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text)
    results = []
    for href, title_html in matches:
        title = _strip_html_text(title_html)
        if title and href:
            results.append({"title": title[:200], "url": href})
        if len(results) >= max(1, min(int(limit or 5), 10)):
            break
    return {"ok": True, "query": q, "results": results, "row_count": len(results)}


def _web_fetch_page(url: str) -> Dict[str, Any]:
    target = str(url or "").strip()
    if not re.match(r"^https?://", target, re.I):
        raise ValueError("url must start with http:// or https://")
    resp = requests.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", resp.text)
    return {"ok": True, "url": target, "final_url": resp.url, "status_code": resp.status_code, "title": _strip_html_text(title_match.group(1))[:200] if title_match else "", "text_sample": _clip_text(_strip_html_text(resp.text), 4000)}


def _approval_enabled() -> bool:
    return str(os.getenv("WEBAGENT_REQUIRE_APPROVAL", "1") or "1").strip().lower() not in ("0", "false", "no", "off")


def _bridge_name() -> str:
    return str(os.getenv("WEBAGENT_BRIDGE_NAME", "WebAgent Local Bridge") or "WebAgent Local Bridge").strip() or "WebAgent Local Bridge"


def _normalize_origin(origin: Any) -> str:
    value = str(origin or "").strip().rstrip("/")
    if not value:
        return ""
    return value if re.match(r"^https?://[^/]+$", value, re.I) else ""


def _request_origin() -> str:
    return _normalize_origin(request.headers.get("Origin"))


def _load_approved_origins() -> List[str]:
    if not APPROVED_ORIGINS_FILE.exists():
        return []
    try:
        raw = json.loads(APPROVED_ORIGINS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    values = raw if isinstance(raw, list) else raw.get("origins", []) if isinstance(raw, dict) else []
    approved: List[str] = []
    seen = set()
    for item in values:
        origin = _normalize_origin(item)
        if origin and origin not in seen:
            seen.add(origin)
            approved.append(origin)
    return approved


def _save_approved_origins(origins: List[str]) -> None:
    clean = []
    seen = set()
    for item in origins:
        origin = _normalize_origin(item)
        if origin and origin not in seen:
            seen.add(origin)
            clean.append(origin)
    APPROVED_ORIGINS_FILE.write_text(json.dumps({"origins": clean}, indent=2), encoding="utf-8")


def _origin_is_approved(origin: str) -> bool:
    if not _approval_enabled():
        return True
    clean = _normalize_origin(origin)
    if not clean:
        return True
    return clean in set(_load_approved_origins())


def _purge_expired_approval_tokens(now: Optional[float] = None) -> None:
    cutoff = float(now if now is not None else time.time())
    with _APPROVAL_TOKENS_LOCK:
        stale = [token for token, meta in _APPROVAL_TOKENS.items() if float(meta.get("expires_at", 0.0) or 0.0) <= cutoff]
        for token in stale:
            _APPROVAL_TOKENS.pop(token, None)


def _create_approval_token(origin: str) -> str:
    clean = _normalize_origin(origin)
    if not clean:
        return ""
    token = secrets.token_urlsafe(24)
    expires_at = time.time() + _APPROVAL_TOKEN_TTL_SECONDS
    _purge_expired_approval_tokens()
    with _APPROVAL_TOKENS_LOCK:
        _APPROVAL_TOKENS[token] = {"origin": clean, "expires_at": expires_at}
    return token


def _approval_record_for_token(token: Any, consume: bool = False) -> Optional[Dict[str, Any]]:
    key = str(token or "").strip()
    if not key:
        return None
    _purge_expired_approval_tokens()
    with _APPROVAL_TOKENS_LOCK:
        record = _APPROVAL_TOKENS.get(key)
        if record and consume:
            _APPROVAL_TOKENS.pop(key, None)
    return dict(record) if isinstance(record, dict) else None


def _bridge_base_url() -> str:
    override = str(os.getenv("WEBAGENT_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if override:
        return override
    return str(request.host_url or "").rstrip("/")


def _approval_url(origin: str) -> str:
    token = _create_approval_token(origin)
    if not token:
        return ""
    return _bridge_base_url() + "/bridge/approve?token=" + token


def _approval_required_payload(origin: str) -> Dict[str, Any]:
    clean = _normalize_origin(origin)
    if clean and not _origin_is_approved(clean):
        _append_approval_log("approval_required", clean, "api access blocked pending local approval")
    payload = {
        "ok": False,
        "approval_required": bool(clean),
        "origin": clean,
        "origin_allowed": _origin_is_approved(clean),
        "bridge_name": _bridge_name(),
        "api_base_url": _bridge_base_url(),
        "error": "Local bridge approval required for this website." if clean else "Origin header is missing.",
    }
    if clean and not payload["origin_allowed"]:
        payload["approval_url"] = _approval_url(clean)
    return payload


def _bridge_manifest_payload(origin: str) -> Dict[str, Any]:
    clean = _normalize_origin(origin)
    origin_allowed = _origin_is_approved(clean)
    payload = {
        "ok": True,
        "service": "local-agent-bridge",
        "bridge_name": _bridge_name(),
        "api_base_url": _bridge_base_url(),
        "discovery_version": 1,
        "origin": clean,
        "origin_allowed": origin_allowed,
        "approval_required": bool(clean) and not origin_allowed and _approval_enabled(),
    }
    if payload["approval_required"]:
        payload["approval_url"] = _approval_url(clean)
    return payload


def _approval_page_html(title: str, body: str) -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>%s</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; background: #f5f0e6; color: #1f1f1f; margin: 0; }
    main { max-width: 720px; margin: 48px auto; padding: 24px; background: #fffdf9; border: 1px solid #d7cdbd; border-radius: 18px; box-shadow: 0 18px 48px rgba(57, 42, 18, 0.12); }
    h1 { margin-top: 0; font-size: 28px; }
    p { line-height: 1.55; }
    code { background: #efe3cf; padding: 2px 6px; border-radius: 6px; }
    .actions { display: flex; gap: 12px; margin-top: 20px; }
    button { border: 0; border-radius: 10px; padding: 12px 18px; font-size: 15px; cursor: pointer; }
    .allow { background: #14532d; color: white; }
    .deny { background: #b42318; color: white; }
    .note { margin-top: 16px; color: #5a4730; font-size: 14px; }
  </style>
</head>
<body>
  <main>
    <h1>%s</h1>
    %s
  </main>
</body>
</html>""" % (html_lib.escape(title), html_lib.escape(title), body)


def _approval_log_path(now: Optional[datetime] = None) -> Path:
    stamp = now or datetime.now()
    return APPROVAL_LOG_DIR / ("approvals-" + stamp.strftime("%Y-%m-%d") + ".txt")


def _append_approval_log(action: str, origin: Any, detail: Any = "") -> None:
    clean_action = str(action or "").strip() or "unknown"
    clean_origin = _normalize_origin(origin) or str(origin or "").strip() or "-"
    clean_detail = str(detail or "").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] action=%s origin=%s" % (timestamp, clean_action, clean_origin)
    if clean_detail:
        line += " detail=%s" % clean_detail.replace("\r", " ").replace("\n", " ")
    try:
        with _approval_log_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def _approval_notify_script(origin: Any, decision: str) -> str:
    payload = json.dumps({
        "type": "webagent-bridge-approval",
        "origin": _normalize_origin(origin),
        "decision": str(decision or "").strip().lower() or "unknown",
    }, ensure_ascii=True)
    return """
<script>
  (function () {
    var payload = %s;
    try {
      if (window.opener && typeof window.opener.postMessage === 'function') {
        window.opener.postMessage(payload, '*');
      }
    } catch (_) {}
    setTimeout(function () {
      try { window.close(); } catch (_) {}
    }, 250);
  })();
</script>
""" % payload


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _gate_bridge_access():
        if request.method == "OPTIONS":
            return ("", 204)
        if request.path in ("/healthz", "/.well-known/webagent-bridge"):
            return None
        if request.path.startswith("/bridge/approve") or request.path.startswith("/bridge/sites"):
            return None
        if not request.path.startswith("/api/"):
            return None
        origin = _request_origin()
        if _origin_is_approved(origin):
            return None
        return jsonify(_approval_required_payload(origin)), 403

    @app.after_request
    def _cors(resp):
        requested_origin = _request_origin()
        allow_origin = str(os.getenv("WEBAGENT_ALLOW_ORIGIN", "") or "").strip()
        if allow_origin and allow_origin != "auto":
            resp.headers["Access-Control-Allow-Origin"] = allow_origin
        elif requested_origin:
            resp.headers["Access-Control-Allow-Origin"] = requested_origin
            resp.headers["Vary"] = "Origin"
        else:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"ok": True, "service": "local-agent-bridge", "bridge_name": _bridge_name()})

    @app.route("/.well-known/webagent-bridge", methods=["GET"])
    def bridge_manifest():
        return jsonify(_bridge_manifest_payload(_request_origin()))

    @app.route("/bridge/approve", methods=["GET", "POST"])
    def bridge_approve():
        if request.method == "GET":
            record = _approval_record_for_token(request.args.get("token"))
            if not record:
                body = "<p>This approval link is invalid or has expired.</p><p class=\"note\">Return to the website and try connecting again.</p>"
                return Response(_approval_page_html("Bridge approval expired", body), mimetype="text/html")
            origin = html_lib.escape(str(record.get("origin") or ""))
            token = html_lib.escape(str(request.args.get("token") or ""))
            body = """
<p><code>%s</code> is asking to use your local agent bridge.</p>
<p>Allow this only for websites you trust. Approved websites can call your local Codex and Claude bridge until you remove them from <code>%s</code>.</p>
<form method="post" class="actions">
  <input type="hidden" name="token" value="%s">
  <button class="allow" type="submit" name="decision" value="allow">Allow site</button>
  <button class="deny" type="submit" name="decision" value="deny">Deny</button>
</form>
<p class="note">This approval link expires in %d minutes.</p>
""" % (origin, html_lib.escape(str(APPROVED_ORIGINS_FILE)), token, max(1, _APPROVAL_TOKEN_TTL_SECONDS // 60))
            return Response(_approval_page_html("Approve local bridge access", body), mimetype="text/html")
        record = _approval_record_for_token(request.form.get("token"), consume=True)
        decision = str(request.form.get("decision") or "").strip().lower()
        if not record:
            body = "<p>This approval request has already expired.</p><p class=\"note\">Go back to the website and reconnect.</p>"
            return Response(_approval_page_html("Bridge approval expired", body), mimetype="text/html")
        origin = _normalize_origin(record.get("origin"))
        if decision == "allow" and origin:
            approved = _load_approved_origins()
            if origin not in approved:
                approved.append(origin)
                _save_approved_origins(approved)
            _append_approval_log("allow", origin, "approved from /bridge/approve")
            body = "<p>Approved <code>%s</code>.</p><p class=\"note\">You can close this tab and return to the website.</p>%s" % (html_lib.escape(origin), _approval_notify_script(origin, "allow"))
            return Response(_approval_page_html("Access approved", body), mimetype="text/html")
        _append_approval_log("deny", origin or "unknown", "denied from /bridge/approve")
        body = "<p>Denied access for <code>%s</code>.</p><p class=\"note\">You can close this tab and return to the website.</p>%s" % (html_lib.escape(origin or "this site"), _approval_notify_script(origin or "this site", "deny"))
        return Response(_approval_page_html("Access denied", body), mimetype="text/html")

    @app.route("/bridge/sites", methods=["GET", "POST"])
    def bridge_sites():
        prefill_origin = _normalize_origin(request.values.get("origin"))
        if request.method == "POST":
            action = str(request.form.get("action") or "").strip().lower()
            origin = _normalize_origin(request.form.get("origin"))
            approved = _load_approved_origins()
            changed = False
            if action == "revoke" and origin and origin in approved:
                approved = [item for item in approved if item != origin]
                changed = True
                _append_approval_log("revoke", origin, "revoked from /bridge/sites")
            elif action == "approve" and origin and origin not in approved:
                approved.append(origin)
                changed = True
                _append_approval_log("manual_approve", origin, "approved from /bridge/sites")
            if changed:
                _save_approved_origins(approved)
        approved_origins = _load_approved_origins()
        origin_rows = []
        for origin in approved_origins:
            safe_origin = html_lib.escape(origin)
            origin_rows.append(
                "<tr><td><code>%s</code></td><td>"
                "<form method=\"post\" style=\"display:inline\">"
                "<input type=\"hidden\" name=\"action\" value=\"revoke\">"
                "<input type=\"hidden\" name=\"origin\" value=\"%s\">"
                "<button class=\"deny\" type=\"submit\">Revoke</button>"
                "</form></td></tr>" % (safe_origin, safe_origin)
            )
        rows_html = "".join(origin_rows) or "<tr><td colspan=\"2\">No approved sites yet.</td></tr>"
        intro_html = ""
        if prefill_origin:
            intro_html = "<p class=\"note\">Protocol launch requested for <code>%s</code>. You can approve it below after the bridge opens.</p>" % html_lib.escape(prefill_origin)
        body = """
<p>Manage websites that can use your local bridge.</p>
%s
<p class="note">Discovery URL: <code>%s/.well-known/webagent-bridge</code></p>
<p class="note">Approval store: <code>%s</code></p>
<form method="post" style="margin:20px 0 28px 0;">
  <input type="hidden" name="action" value="approve">
  <label for="origin" style="display:block;margin-bottom:8px;">Manually approve a website origin</label>
  <input id="origin" name="origin" type="text" value="%s" placeholder="https://example.com" style="width:100%%;max-width:420px;padding:10px 12px;border:1px solid #c8b79a;border-radius:10px;">
  <div class="actions">
    <button class="allow" type="submit">Approve origin</button>
  </div>
</form>
<table style="width:100%%;border-collapse:collapse;">
  <thead>
    <tr><th style="text-align:left;border-bottom:1px solid #d7cdbd;padding:8px 0;">Approved origin</th><th style="text-align:left;border-bottom:1px solid #d7cdbd;padding:8px 0;">Action</th></tr>
  </thead>
  <tbody>%s</tbody>
</table>
        """ % (intro_html, html_lib.escape(_bridge_base_url()), html_lib.escape(str(APPROVED_ORIGINS_FILE)), html_lib.escape(prefill_origin or ""), rows_html)
        return Response(_approval_page_html("Manage approved sites", body), mimetype="text/html")

    @app.route("/bridge/shutdown", methods=["POST"])
    def bridge_shutdown():
        remote = str(request.remote_addr or "").strip().lower()
        if remote not in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"):
            return jsonify({"ok": False, "error": "shutdown only allowed from localhost"}), 403

        def _terminate() -> None:
            time.sleep(0.2)
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                os._exit(0)

        threading.Thread(target=_terminate, daemon=True).start()
        return jsonify({"ok": True, "stopping": True})

    @app.route("/api/tools/manifest", methods=["GET"])
    def api_tools_manifest():
        return jsonify({"ok": True, "tools": _bridge_tool_manifests(), "count": len(_bridge_tool_manifests())})

    @app.route("/api/tools/execute", methods=["POST"])
    def api_tools_execute():
        payload = request.get_json(silent=True) or {}
        tool_name = str(payload.get("tool") or "").strip()
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        try:
            return jsonify(_execute_bridge_tool(tool_name, args))
        except Exception as exc:
            return jsonify({"ok": False, "tool": tool_name, "error": str(exc)}), 400

    @app.route("/api/codex/status", methods=["GET"])
    def api_codex_status():
        cli_path = _codex_cli_path()
        try:
            chk = subprocess.run([cli_path, "--version"], capture_output=True, text=True, timeout=15, **_hidden_subprocess_kwargs())
            installed = chk.returncode == 0
            version = (chk.stdout or chk.stderr or "").strip()
        except Exception as exc:
            installed = False
            version = str(exc)
        return jsonify({"ok": True, "configured": installed, "cli": cli_path, "version": version, "model": "codex-cli-local"})

    @app.route("/api/codex/cancel", methods=["POST"])
    def api_codex_cancel():
        with _ACTIVE_CODEX_LOCK:
            proc = _ACTIVE_CODEX_PROC
        if proc is not None and proc.poll() is None:
            killed = _kill_process_tree(proc)
            return jsonify({"ok": True, "killed": killed})
        return jsonify({"ok": True, "killed": False, "reason": "no active process"})

    @app.route("/api/codex/chat", methods=["POST"])
    def api_codex_chat():
        payload = request.get_json(silent=True) or {}
        messages = payload.get("messages") or []
        app_context = payload.get("app_context") if isinstance(payload.get("app_context"), dict) else {}
        fast_mode = True if payload.get("fast_mode") is None else bool(payload.get("fast_mode"))
        started = time.time()
        accepts_stream = "text/event-stream" in str(request.headers.get("Accept") or "").lower()
        wants_stream = bool(payload.get("stream")) or accepts_stream
        if wants_stream:
            prompt = _build_prompt(messages=messages, app_context=app_context)

            def generate():
                final_result = None
                error_msg = None
                native_activity: List[str] = []
                for event in _codex_exec_streaming(prompt, "codex_response_schema.json", timeout=0):
                    if isinstance(event, dict) and event.get("_event") == "error":
                        error_msg = str(event.get("error") or "unknown error")
                        break
                    if isinstance(event, dict) and event.get("_event") == "done":
                        final_result = event.get("result") or {}
                        break
                    desc = _describe_native_progress_event(event)
                    if desc:
                        native_activity.append(desc)
                        if len(native_activity) > 60:
                            native_activity = native_activity[-60:]
                    yield "event: progress\ndata: %s\n\n" % json.dumps(event, ensure_ascii=True)
                if error_msg:
                    yield "event: error\ndata: %s\n\n" % json.dumps({"ok": False, "error": error_msg, "duration_ms": int((time.time() - started) * 1000)}, ensure_ascii=True)
                    return
                out = final_result or {}
                if out and not fast_mode:
                    out = _verify_final_response(out, messages=messages, app_context=app_context, native_activity=native_activity)
                yield "event: done\ndata: %s\n\n" % json.dumps({"ok": True, "duration_ms": int((time.time() - started) * 1000), **out}, ensure_ascii=True)

            return Response(generate(), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
        try:
            out = _codex_exec_structured(_build_prompt(messages=messages, app_context=app_context), "codex_response_schema.json", timeout=180)
            if not fast_mode:
                out = _verify_final_response(out, messages=messages, app_context=app_context)
            return jsonify({"ok": True, "duration_ms": int((time.time() - started) * 1000), **out})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "duration_ms": int((time.time() - started) * 1000)}), 500

    @app.route("/api/claude/status", methods=["GET"])
    def api_claude_status():
        cli_path = _claude_cli_path()
        try:
            chk = subprocess.run([cli_path, "--version"], capture_output=True, text=True, timeout=15, **_hidden_subprocess_kwargs())
            installed = chk.returncode == 0
            version = (chk.stdout or chk.stderr or "").strip()
        except Exception as exc:
            installed = False
            version = str(exc)
        return jsonify({"ok": True, "installed": installed, "configured": installed, "cli": cli_path, "version": version, "model": "claude-code-local"})

    @app.route("/api/claude/cancel", methods=["POST"])
    def api_claude_cancel():
        with _ACTIVE_CLAUDE_LOCK:
            proc = _ACTIVE_CLAUDE_PROC
        if proc is not None and proc.poll() is None:
            killed = _kill_process_tree(proc)
            return jsonify({"ok": True, "killed": killed})
        return jsonify({"ok": True, "killed": False, "reason": "no active process"})

    @app.route("/api/claude/chat", methods=["POST"])
    def api_claude_chat():
        payload = request.get_json(silent=True) or {}
        messages = payload.get("messages") or []
        app_context = payload.get("app_context") if isinstance(payload.get("app_context"), dict) else {}
        started = time.time()
        accepts_stream = "text/event-stream" in str(request.headers.get("Accept") or "").lower()
        wants_stream = bool(payload.get("stream")) or accepts_stream
        if wants_stream:
            import queue

            q: "queue.Queue[Any]" = queue.Queue()

            def _run():
                try:
                    q.put(("done", _claude_cli_request(messages=messages, app_context=app_context)))
                except Exception as exc:
                    q.put(("error", str(exc)))

            threading.Thread(target=_run, daemon=True).start()

            def generate():
                yield "event: progress\ndata: %s\n\n" % json.dumps({"type": "thinking", "text": "Asking Claude Code..."}, ensure_ascii=True)
                next_heartbeat_at = time.time() + 5.0
                while True:
                    try:
                        kind, payload_ = q.get(timeout=0.5)
                        break
                    except queue.Empty:
                        now = time.time()
                        if now >= next_heartbeat_at:
                            elapsed = int(now - started)
                            message = "Still waiting for Claude Code..."
                            if elapsed >= 10:
                                message = "Still waiting for Claude Code (%ds)..." % elapsed
                            yield "event: progress\ndata: %s\n\n" % json.dumps({"type": "heartbeat", "text": message}, ensure_ascii=True)
                            next_heartbeat_at = now + 5.0
                if kind == "done":
                    yield "event: done\ndata: %s\n\n" % json.dumps({"ok": True, "duration_ms": int((time.time() - started) * 1000), **payload_}, ensure_ascii=True)
                else:
                    yield "event: error\ndata: %s\n\n" % json.dumps({"ok": False, "error": payload_, "duration_ms": int((time.time() - started) * 1000)}, ensure_ascii=True)

            return Response(generate(), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
        try:
            out = _claude_cli_request(messages=messages, app_context=app_context)
            return jsonify({"ok": True, "duration_ms": int((time.time() - started) * 1000), **out})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "duration_ms": int((time.time() - started) * 1000)}), 500

    @app.route("/api/db-helper/status", methods=["GET"])
    def api_db_status():
        try:
            _db_connect().close()
            return jsonify({"ok": True, "available": True, "configured": bool(os.getenv("SQL_CONN_STR")), "conn_error": "", "read_only": True})
        except Exception as exc:
            return jsonify({"ok": True, "available": False, "configured": bool(os.getenv("SQL_CONN_STR")), "conn_error": str(exc), "read_only": True})

    @app.route("/api/db-helper/tables", methods=["GET"])
    def api_db_tables():
        sql = "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME"
        try:
            return jsonify({"ok": True, **_db_helper_run_query(sql, limit=500)})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/db-helper/query", methods=["POST"])
    def api_db_query():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify({"ok": True, **_db_helper_run_query(str(payload.get("sql") or "").strip(), limit=payload.get("limit"))})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/db-helper/export-csv", methods=["POST"])
    def api_db_export():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(_db_helper_export_csv(str(payload.get("sql") or "").strip(), payload.get("path")))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/web/search", methods=["POST"])
    def api_web_search():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(_web_search(payload.get("query"), limit=payload.get("limit")))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except requests.RequestException as exc:
            return jsonify({"ok": False, "error": "web search failed: " + str(exc)}), 502

    @app.route("/api/web/fetch", methods=["POST"])
    def api_web_fetch():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(_web_fetch_page(payload.get("url")))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except requests.RequestException as exc:
            return jsonify({"ok": False, "error": "page fetch failed: " + str(exc)}), 502

    return app


def main() -> None:
    app = create_app()
    host = str(os.getenv("WEBAGENT_HOST", "127.0.0.1") or "127.0.0.1")
    port = int(os.getenv("WEBAGENT_PORT", "8787") or 8787)
    app.run(host=host, port=port, debug=False)
