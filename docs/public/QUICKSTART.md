# Quickstart

This project has two separate installation paths.

## 1. Website Owner Quickstart

Use this if you want to embed the assistant into a website.

### Install

```html
<script src="https://cdn.jsdelivr.net/npm/@webagent/widget/dist/agent-widget.js"></script>
```

### Provide a bridge

```html
<script>
  window.MySiteAgentBridge = {
    getContext() {
      return {
        title: document.title,
        path: location.pathname,
        url: location.href
      };
    },
    getVisibleTextSample() {
      return document.body.innerText.slice(0, 4000);
    }
  };
</script>
```

### Mount the widget

```html
<div id="agent-root"></div>
<script>
  AgentWidget.init({
    target: "#agent-root",
    bridge: window.MySiteAgentBridge,
    defaultBackend: "codex"
  });
</script>
```

### Result

- If the site does not set `apiBaseUrl`, the widget looks for the user's local bridge.
- If the site does set `apiBaseUrl`, the widget uses the site backend instead.

## 2. End User Quickstart

Use this if you want websites to talk to your local Codex or Claude agent.

Direct downloads in this repo:

- Windows installer: `server/dist/windows/WebAgentBridgeSetup.exe`
- Python wheel: `server/dist/local_agent_bridge-0.1.0-py3-none-any.whl`
- Python source package: `server/dist/local_agent_bridge-0.1.0.tar.gz`
- widget npm tarball: `widget/webagent-widget-0.1.0.tgz`
- checksums: `server/dist/SHA256SUMS.txt`, `widget/SHA256SUMS.txt`

### Windows

Run:

- `server/dist/windows/WebAgentBridgeSetup.exe`

Then choose:

- `Install` / `Reinstall`

After install, use the desktop app to:

- start the bridge
- stop the bridge
- open approved sites
- open logs

### macOS

Current macOS usage is source-based.

Install:

```bash
cd server
python3 -m pip install .
```

Run:

```bash
local-agent-bridge
```

Optional Python desktop companion after `pip install .`:

```bash
local-agent-bridge-app
```

Notes:

- `local-agent-bridge` is the required local service
- `local-agent-bridge-app` is only a convenience GUI
- it is not a packaged native macOS app yet
- it may require a Python build that includes `tkinter`

Optional protocol registration:

```bash
local-agent-bridge-install
```

### Linux

Packaged setup bundle:

```bash
cd server
chmod +x ./build/build_linux.sh
./build/build_linux.sh
chmod +x ./build/build_linux_setup.sh
./build/build_linux_setup.sh
```

Then give the user:

- `server/dist/linux/WebAgentBridgeSetup.tar.gz`

User install flow:

```bash
tar -xzf WebAgentBridgeSetup.tar.gz
./installer_ui.sh
```

Source-based fallback:

```bash
cd server
python3 -m pip install .
```

Run:

```bash
local-agent-bridge
```

Optional Python desktop companion after install:

```bash
local-agent-bridge-app
```

Notes:

- `local-agent-bridge` is the required local service
- `local-agent-bridge-app` is only a convenience GUI
- on Linux it usually runs from the installed Python package unless you build your own setup bundle
- depending on distro, you may need Tk packages for it

Optional protocol registration:

```bash
local-agent-bridge-install
```

### Approve sites

Open:

- `http://127.0.0.1:8787/bridge/sites`

That page lets you:

- see approved websites
- manually approve an origin
- revoke a website

### Logs

Runtime logs live in:

- Windows: `%USERPROFILE%\\.local-agent-bridge\\runtime_logs`
- macOS / Linux: `~/.local-agent-bridge/runtime_logs`

Key files:

- `desktop_app.log`
- `bridge_server.log`

## 3. Hosted Backend Mode

If you are a website owner and want to force your own backend:

```js
AgentWidget.init({
  target: "#agent-root",
  bridge: window.MySiteAgentBridge,
  apiBaseUrl: "https://agent.example.com",
  defaultBackend: "codex"
});
```

In that mode, the local bridge is bypassed.
