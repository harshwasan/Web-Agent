# Codex / Claude as an Embedded Widget

This doc describes how to turn the current Codex integration into a **reusable embedded widget** that can connect to **any user’s local Codex or Claude** CLI, and be dropped into other apps.

---

## Goals

1. **Portable widget** – One UI bundle (drawer + chat + actions) that can be embedded in any host page.
2. **Any user’s local agent** – Connect to whatever Codex or Claude CLI is installed (no hardcoded paths).
3. **Pluggable host** – The host app supplies (a) an “agent bridge” for context and actions, and (b) optionally its own backend that runs the CLI.

---

## Architecture (current vs widget)

| Piece | Current (YahooDataFetcher) | Widget target |
|-------|----------------------------|----------------|
| **UI** | `codex_extension.js` assumes `window.YahooAppAgent` | Use a **pluggable bridge** (e.g. `window.CodexAgentBridge` or config) |
| **Context + actions** | `yahoo_app_agent.js` (Yahoo-specific) | Host provides an object that implements the **bridge interface** |
| **Backend** | Flask in `web_ui.py`, hardcoded Codex path | **Configurable** CLI path, doc paths, and optional app instructions |
| **API** | `POST /api/codex/chat` (same origin) | Configurable **base URL** so widget can talk to host or a standalone agent service |

---

## Changes Required

### 1. Backend (agent server / Flask)

**1.1 Configurable Codex CLI path**

- **Now:** `_codex_cli_path()` returns `D:\setups\codex\npm-global\codex.cmd`.
- **Change:** Prefer env, then PATH, then platform defaults:
  - `CODEX_CLI_PATH` – if set, use it.
  - Else run `codex` (or `codex.cmd` on Windows) via PATH.
  - Optional: fallback to `~/.codex/codex.cmd` or common install dirs.
- **Same idea for Claude** if you support it: `CLAUDE_CODE_EXE` already exists; document it and optionally add PATH fallback.

**1.2 Configurable context docs**

- **Now:** Docs are fixed under `APP_ROOT/docs` (`CODEX_AGENT_CONTEXT.md`, etc.).
- **Change:** Already partially env-driven: `CODEX_AGENT_DOC_PATHS` (semicolon-separated). For a generic widget:
  - Default to **empty** or a minimal “widget” doc when not in YahooDataFetcher.
  - Host app sets `CODEX_AGENT_DOC_PATHS` to inject its own context (or the server passes doc paths in config).

**1.3 Optional app-specific system prompt**

- **Now:** System prompt in `_codex_request()` is Yahoo-specific (AlphaEOD, tables, etc.).
- **Change:** Split into:
  - **Core instructions** (JSON schema, allowed action types, “no raw HTML”, etc.) – stay in code.
  - **App instructions** – from a file or env (e.g. `CODEX_AGENT_INSTRUCTIONS_PATH`) or from an API parameter. If missing, use a short generic line (“You are Codex embedded in this app.”).

**1.4 Response contract unchanged**

- Keep returning `{ ok, message, actions, ... }` so any host using the widget can stay compatible.

---

### 2. Frontend (widget)

**2.1 Pluggable agent bridge**

- **Now:** `codex_extension.js` uses `window.YahooAppAgent` for:
  - `getContext(allowUiAccess)`
  - `getVisibleTextSample()`
  - Action methods: `clickSelector`, `setInputValue`, `navigateStock`, `queryDb`, `exportQueryToCsv`, `fetchDomHtml`, `webSearch`, `fetchWebPage`, `fetchDbTables`, `fetchDbStatus`
- **Change:** Use a **bridge name from config**, with fallback:
  - e.g. `window.CodexWidgetConfig = { agentBridge: 'YahooAppAgent' }` or `agentBridge: window.MyAppBridge`.
  - Widget reads `agentBridge` and uses that object. If a string, use `window[agentBridge]`.
  - Host page does: `window.MyAppBridge = { getContext, getVisibleTextSample, clickSelector, ... }` (only the methods it supports; unsupported actions can no-op or return an error).

**2.2 Configurable API base URL**

- **Now:** All `fetch()` calls are same-origin (e.g. `/api/codex/chat`).
- **Change:** Add `apiBaseUrl` to widget config (e.g. `''` for same origin, or `'https://myapp.com'`). Prepend it to every agent API path so the widget can talk to:
  - The same server (default), or
  - A different “agent proxy” server that runs Codex/Claude.

**2.2.1 Runtime backend selection**

- The widget should support choosing `codex` or `claude` at runtime.
- Store the selected backend in local storage so the page reopens on the last used backend.
- Route status/chat calls to `/api/codex/*` or `/api/claude/*` based on that selection.

**2.2.2 Host-provided docs**

- A host page can advertise default docs for any agent through:
  - `window.CodexWidgetConfig.hostedDocs = [{ href, title }]`, or
  - `<link rel="agent-doc" href="...">`, or
  - `<a data-agent-doc href="...">...</a>`
- The widget should collect those links and include them in `app_context.hosted_doc_links`.
- The backend prompt should surface those links so the agent can use them directly or fetch them with `fetchWebPage` when appropriate.

**2.3 Optional: which actions are allowed**

- **Now:** Backend and frontend both assume a fixed list of action types.
- **Change (optional):** Backend could accept `allowed_actions` in the request or config and trim the system prompt + schema. Frontend already only calls methods that exist on the bridge; host can leave unsupported methods undefined.

---

### 3. Host integration (embedder)

For a **new app** that embeds the widget:

1. **Include the widget script(s)**  
   - One bundle: widget UI + optional “generic” bridge stub, or  
   - Widget script + host’s own bridge script.

2. **Provide the bridge**  
   - Implement the interface (at least `getContext`, and any of the action methods the app supports).  
   - Set `window.CodexAgentBridge = myBridge` (or whatever name is configured).

3. **Serve or point to the agent API**  
   - **Option A:** Host’s backend has a route that runs Codex/Claude (same as current Flask route); set `apiBaseUrl: ''` or the host’s origin.  
   - **Option B:** Separate “agent proxy” service (e.g. small Node/Python server that only runs the CLI); host and widget point `apiBaseUrl` at that service (CORS must allow the host origin).

4. **Configure the agent server** (if the host runs it)  
   - Set `CODEX_CLI_PATH` (or rely on PATH).  
   - Set `CODEX_AGENT_DOC_PATHS` to the host’s context docs, if any.  
   - Optionally set `CODEX_AGENT_INSTRUCTIONS_PATH` for app-specific instructions.

---

## File-level checklist

| File | Change |
|------|--------|
| `web_ui.py` | Codex/Claude CLI path from env + PATH; doc paths from env (default empty for generic); optional instructions file or param. |
| `static/codex_extension.js` | Read bridge from config (`CodexWidgetConfig.agentBridge`); resolve `window[bridgeName]`; prepend `apiBaseUrl` to fetch URLs; handle missing bridge gracefully. |
| `static/codex_extension.js` | Add backend selector (`codex` / `claude`) and include host-provided doc links in `app_context`. |
| New (optional) | `static/codex-widget-config.js` – default `CodexWidgetConfig` so embedders can override. |
| New (optional) | Standalone “agent proxy” server (e.g. `agent_proxy.py`) that only does POST → run CLI → return JSON, for use without Flask. |
| `docs/CODEX_AGENT_CONTEXT.md` | Add a short “Embedded widget” section pointing to this doc. |

---

## Summary

- **Backend:** Make CLI path and doc paths configurable (env + PATH); keep response format; optionally make system prompt app-specific.
- **Frontend:** Pluggable agent bridge (config-driven) and configurable API base URL so the same widget can run on any host and talk to any backend that implements the same contract.
- **Host:** Implements the bridge interface and either runs the agent server or points the widget at an existing one. No hardcoded Yahoo or single-machine paths.

With these changes, the integration becomes an **embedded widget** that can connect to **any user’s local Codex/Claude** and any host app that provides the bridge and (optionally) the agent API.
