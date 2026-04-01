# `local-agent-bridge`

Local companion bridge for the WebAgent browser widget.

This package exposes the generic agent endpoints used by the widget and runs the user's own local Codex or Claude agent:

- `/api/codex/status`
- `/api/codex/chat`
- `/api/codex/cancel`
- `/api/claude/status`
- `/api/claude/chat`
- `/api/claude/cancel`
- `/api/db-helper/*`
- `/api/web/*`

It also exposes:

- `/.well-known/webagent-bridge`
- `/bridge/approve`
- `/bridge/sites`

## Install

```bash
pip install local-agent-bridge
```

Direct package files committed in this repo:

- [`dist/local_agent_bridge-0.1.0-py3-none-any.whl`](./dist/local_agent_bridge-0.1.0-py3-none-any.whl)
- [`dist/local_agent_bridge-0.1.0.tar.gz`](./dist/local_agent_bridge-0.1.0.tar.gz)
- checksums: [`dist/SHA256SUMS.txt`](./dist/SHA256SUMS.txt)

Optional SQL Server support:

```bash
pip install "local-agent-bridge[sqlserver]"
```

## Platform Install Notes

### Windows

Current easiest path:

- run [`dist/windows/WebAgentBridgeSetup.exe`](./dist/windows/WebAgentBridgeSetup.exe)

That setup currently gives you:

- install / reinstall
- uninstall
- protocol registration for `webagent://`

After install, launch the app from the installed shortcut or by running the installed desktop companion.

Other Windows files in the repo:

- [`dist/windows/WebAgentBridge.exe`](./dist/windows/WebAgentBridge.exe)
- [`dist/windows/webagent_protocol_built_exe.reg`](./dist/windows/webagent_protocol_built_exe.reg)

### macOS

Current macOS path is source-based, not a signed `.app` yet.

Recommended prerequisites:

- Python 3.10+
- `pip`
- a Python build that includes `tkinter`

Install:

```bash
cd server
python3 -m pip install .
```

Run the local bridge:

```bash
local-agent-bridge
```

Optional Python desktop companion after install:

```bash
local-agent-bridge-app
```

Optional user-scoped protocol registration:

```bash
local-agent-bridge-install
```

Management page:

- `http://127.0.0.1:8787/bridge/sites`

Notes:

- `local-agent-bridge` is the required local service
- `local-agent-bridge-app` is only a convenience GUI for start/stop/status/logs
- on macOS today it runs from the installed Python package, not from a packaged native `.app`
- if `local-agent-bridge-app` fails with a Tk error, install or use a Python distribution that includes `tkinter`

### Linux

Current Linux path supports both source-based install and a lightweight setup bundle, but not polished distro-native packaging yet.

Install:

```bash
cd server
python3 -m pip install .
```

Run the local bridge:

```bash
local-agent-bridge
```

Optional Python desktop companion after install:

```bash
local-agent-bridge-app
```

Optional user-scoped protocol registration:

```bash
local-agent-bridge-install
```

Notes:

- `local-agent-bridge` is the required local service
- `local-agent-bridge-app` is only a convenience GUI for start/stop/status/logs
- on Linux today it usually runs from the installed Python package unless you build your own bundled setup
- depending on distro, you may need Tk packages for the desktop companion

Packaged Linux setup bundle:

```bash
chmod +x ./build/build_linux.sh
./build/build_linux.sh
chmod +x ./build/build_linux_setup.sh
./build/build_linux_setup.sh
```

This produces:

- `server/dist/linux/WebAgentBridgeSetup.tar.gz`

Typical end-user flow on Linux:

```bash
tar -xzf WebAgentBridgeSetup.tar.gz
./installer_ui.sh
```

## Run

```bash
local-agent-bridge
```

Optional Python desktop companion:

```bash
local-agent-bridge-app
```

Run the optional Python desktop companion in tray/background mode:

```bash
local-agent-bridge-app --tray
```

Install protocol registration for the current user:

```bash
local-agent-bridge-install
```

Windows `.reg` fallback:

```bash
local-agent-bridge-install write-reg
```

Windows one-click installer build:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_windows.ps1
powershell -ExecutionPolicy Bypass -File .\build\build_windows_installer.ps1
```

Default address:

- `http://127.0.0.1:8787`

The widget can auto-discover this address by calling:

- `http://127.0.0.1:8787/.well-known/webagent-bridge`

That discovery endpoint returns the active `api_base_url`, so the widget does not need a host page to hardcode `apiBaseUrl`.

## Protocol Launch Flow

This package also includes a protocol handler entrypoint:

```bash
local-agent-bridge-protocol "webagent://open-bridge"
```

Supported protocol URLs:

- `webagent://open-bridge`
- `webagent://open-bridge?origin=https%3A%2F%2Fexample.com`
- `webagent://approve-site?origin=https%3A%2F%2Fexample.com`

What it does:

- ensures the local bridge is running
- opens the local bridge management page in the browser
- if an `origin` is present, pre-fills that origin on `/bridge/sites`

To make websites launch the local bridge directly, the installed desktop/bridge app still has to register the `webagent://` protocol with the OS. The widget can then open `webagent://open-bridge` when localhost discovery fails.

The lightweight desktop app is intended to be that installed companion:

- starts the local bridge if needed
- shows Codex/Claude readiness
- opens the approved-sites page
- opens approval logs
- can be used as the `webagent://` protocol target

### What `local-agent-bridge-install` does

- Windows:
  registers `webagent://` in `HKCU\Software\Classes\webagent`
- macOS:
  creates `~/Applications/WebAgent Bridge.app` with `webagent` URL-scheme support
- Linux:
  creates `~/.local/share/applications/webagent-bridge.desktop` and registers `x-scheme-handler/webagent`

This keeps the install path light and user-scoped instead of requiring a heavy platform installer.

## Runtime Logs

Runtime logs are written under the local bridge data directory.

Current locations:

- Windows: `%USERPROFILE%\\.local-agent-bridge\\runtime_logs`
- macOS: `~/.local-agent-bridge/runtime_logs`
- Linux: `~/.local-agent-bridge/runtime_logs`

Important files:

- `desktop_app.log`
- `bridge_server.log`

## Native Binary Builds

PyInstaller build scripts are included:

- `build/build_windows.ps1`
- `build/build_macos.sh`
- `build/build_linux.sh`

Build details are documented in:

- `build/BUILD_BINARIES.md`
- tracked in this repo at [`build/BUILD_BINARIES.md`](./build/BUILD_BINARIES.md)

## Approval and Management

New websites are blocked from using the local bridge until the user approves them locally.

Approval manager:

- `http://127.0.0.1:8787/bridge/sites`

That page lets the user:

- see approved websites
- manually approve an origin
- revoke a website

Daily approval audit logs are written to:

- `~/.local-agent-bridge/approval_logs/approvals-YYYY-MM-DD.txt`

## Environment

Copy `.env.example` and set what you need:

- `WEBAGENT_HOST`
- `WEBAGENT_PORT`
- `WEBAGENT_PUBLIC_BASE_URL`
- `WEBAGENT_REQUIRE_APPROVAL`
- `WEBAGENT_BRIDGE_NAME`
- `WEBAGENT_ALLOW_ORIGIN`
- `CODEX_CLI_PATH`
- `CLAUDE_CODE_EXE`
- `CODEX_VERIFY_FINAL`
- `CODEX_AGENT_DOC_PATHS`
- `CODEX_AGENT_INSTRUCTIONS_PATH`
- `SQL_CONN_STR`

## Intended Deployment Model

- Website owners embed `@webagent/widget` in their site.
- If the site does not force its own `apiBaseUrl`, the widget auto-discovers a running `local-agent-bridge` on the user's machine.
- If the site does set `apiBaseUrl`, that site-provided agent wins and the widget uses the site's backend.
- The host page provides a bridge object for page context and safe UI actions.

## Notes

- The browser widget does not run Codex or Claude directly.
- `local-agent-bridge` is the component that talks to local CLI tools.
- New websites must be approved locally before they can use the bridge.
- CORS is controlled by `WEBAGENT_ALLOW_ORIGIN`, but approval is enforced separately per website origin when `WEBAGENT_REQUIRE_APPROVAL=1`.
