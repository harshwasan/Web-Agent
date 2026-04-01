# -*- coding: ascii -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _resolve_text_save_path(raw_path: Any, context: Dict[str, Any]) -> Path:
    value = str(raw_path or "").strip().replace("\\", "/")
    if not value:
        raise ValueError("path is required")
    downloads_dir = Path(context.get("downloads_dir") or (Path.home() / "Downloads")).expanduser().resolve()
    data_dir = Path(context.get("data_dir") or (Path.home() / ".local-agent-bridge")).expanduser().resolve()
    default_root = downloads_dir if downloads_dir.exists() else data_dir
    allowed_roots = [downloads_dir, data_dir]

    if value.lower().startswith("downloads/"):
        full_path = (downloads_dir / value.split("/", 1)[1]).resolve()
    elif value.lower().startswith("data/"):
        full_path = (data_dir / value.split("/", 1)[1]).resolve()
    else:
        candidate = Path(value).expanduser()
        full_path = candidate.resolve() if candidate.is_absolute() else (default_root / candidate).resolve()

    suffix = full_path.suffix.lower()
    if suffix not in (".txt", ".md", ".csv", ".json"):
        raise ValueError("only .txt, .md, .csv, and .json are allowed")
    if not any(root == full_path or root in full_path.parents for root in allowed_roots):
        raise ValueError("path must stay within Downloads or the bridge data folder")
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path


def _save_text_file(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    full_path = _resolve_text_save_path(args.get("path"), context)
    content = str(args.get("content") or "")
    overwrite = bool(args.get("overwrite"))
    if full_path.exists() and not overwrite:
        raise ValueError("file already exists; pass overwrite=true to replace it")
    full_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "saved_path": str(full_path),
        "bytes_written": len(content.encode("utf-8")),
        "overwrite": overwrite,
    }


def register_tools(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": "saveTextFile",
            "description": "Save plain text, markdown, CSV, or JSON into Downloads or the bridge data folder.",
            "args_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path under Downloads/ or data/, or an absolute path within those approved roots."},
                    "content": {"type": "string", "description": "File content to write."},
                    "overwrite": {"type": "boolean", "description": "Set true to replace an existing file."},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            "permissions": ["local_files_write"],
            "handler": _save_text_file,
        }
    ]
