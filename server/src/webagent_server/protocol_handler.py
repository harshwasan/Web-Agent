from __future__ import annotations

import sys
from typing import Optional

from .bridge_runtime import ensure_bridge_running, open_browser_url, parse_protocol_url, protocol_target_url


def handle_protocol_url(raw_url: str) -> int:
    protocol_data = parse_protocol_url(raw_url)
    if not protocol_data.get("action"):
        return 2
    if not ensure_bridge_running():
        return 3
    return 0 if open_browser_url(protocol_target_url(protocol_data)) else 4


def main(argv: Optional[list[str]] = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        raise SystemExit("Usage: local-agent-bridge-protocol webagent://open-bridge")
    raise SystemExit(handle_protocol_url(args[0]))
