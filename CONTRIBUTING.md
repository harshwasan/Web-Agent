# Contributing

## Scope

This repo has two primary surfaces:

- `widget/`: the embeddable browser widget
- `server/`: the local bridge and desktop companion

Keep changes scoped to the active public project layout. Do not add new work to `deprecated/`.

## Local Development

### Widget

Use the files in [`widget/`](./widget). The distributable widget currently lives in `widget/dist/agent-widget.js`.

### Server

```bash
cd server
pip install -e .[build]
```

Run the bridge:

```bash
local-agent-bridge
```

Run the desktop companion:

```bash
local-agent-bridge-app
```

## Verification

Typical checks:

```bash
python -m py_compile server/src/webagent_server/*.py
node --check widget/dist/agent-widget.js
```

Windows build flow:

```powershell
cd server
powershell -ExecutionPolicy Bypass -File .\build\build_windows.ps1
powershell -ExecutionPolicy Bypass -File .\build\build_windows_installer.ps1
```

## Pull Requests

Please keep pull requests focused and easy to review:

- explain the problem and the change
- mention user-facing behavior changes
- note any packaging or installer impact
- include verification steps you ran

## Design Notes

- Website-specific actions belong in the widget bridge layer.
- Local agent execution belongs in the server/local bridge layer.
- Avoid coupling new public features to archived code under `deprecated/`.
