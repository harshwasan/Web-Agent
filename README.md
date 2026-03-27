# WebAgent

Embeddable website agent UI plus a user-run local bridge for Codex and Claude.

WebAgent is built around two separate surfaces:

- `widget/`: a browser-side widget that website owners embed on their pages
- `server/`: a local companion app and bridge that end users run on their own machine

That split lets websites expose safe page-specific actions while users keep model execution under their own control.

## Why This Exists

Browsers cannot directly:

- start local CLI tools
- access a user's shell
- launch local agent runtimes safely

WebAgent bridges that gap with a local bridge on `localhost` plus a website widget that can either:

- auto-discover the user's local bridge, or
- use a site-provided backend if the website owner wants to force one

## Architecture

1. A website embeds the widget.
2. The website exposes page context and safe UI actions through a small JS bridge.
3. The widget connects to either:
   - the user's local bridge, or
   - a site-provided backend via `apiBaseUrl`
4. The backend runs Codex or Claude and returns messages plus structured website actions.
5. The widget shows progress, asks for approval when required, and executes allowed actions in the page.

## Two Audiences

### Website owners

You use the widget package in [`widget/`](./widget).

You provide:

- a mount target
- a small JS bridge with page context and safe actions
- optionally your own backend URL

### End users

You install the local bridge package in [`server/`](./server).

That package provides:

- a local HTTP bridge for the widget
- a lightweight desktop companion app
- protocol handling for `webagent://`
- local approval controls for trusted websites

Current platform state:

- Windows: packaged setup flow available
- macOS: source-based install/run path documented
- Linux: packaged setup bundle flow added

## Quick Start

If you want direct packaged downloads from this repository, see [`docs/public/DOWNLOADS.md`](./docs/public/DOWNLOADS.md).

### Website owners

```html
<div id="agent-root"></div>
<script src="https://cdn.jsdelivr.net/npm/@webagent/widget/dist/agent-widget.js"></script>
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

  AgentWidget.init({
    target: "#agent-root",
    bridge: window.MySiteAgentBridge,
    defaultBackend: "codex"
  });
</script>
```

If you do not set `apiBaseUrl`, the widget will try to auto-discover the user's local bridge.

If you want to force your own backend:

```js
AgentWidget.init({
  target: "#agent-root",
  bridge: window.MySiteAgentBridge,
  apiBaseUrl: "https://agent.example.com",
  defaultBackend: "codex"
});
```

### End users

Windows:

- download and run [`server/dist/windows/WebAgentBridgeSetup.exe`](./server/dist/windows/WebAgentBridgeSetup.exe)

Python package files:

- [`server/dist/local_agent_bridge-0.1.0-py3-none-any.whl`](./server/dist/local_agent_bridge-0.1.0-py3-none-any.whl)
- [`server/dist/local_agent_bridge-0.1.0.tar.gz`](./server/dist/local_agent_bridge-0.1.0.tar.gz)

Widget package tarball:

- [`widget/webagent-widget-0.1.0.tgz`](./widget/webagent-widget-0.1.0.tgz)

Linux:

- extract and run the packaged Linux setup bundle built from `server/dist/linux/WebAgentBridgeSetup.tar.gz`

macOS:

```bash
cd server
python3 -m pip install .
local-agent-bridge
```

Optional desktop companion on macOS / Linux:

```bash
local-agent-bridge-app
```

Default local address:

- `http://127.0.0.1:8787`

Local approval manager:

- `http://127.0.0.1:8787/bridge/sites`

## Security Model

The core security boundary is:

- discovery is allowed
- agent API access is blocked until the website origin is approved locally

When a site first tries to use the local bridge:

1. the bridge returns `approval_required`
2. the widget opens a local approval flow
3. the user allows or denies the site
4. the decision is stored locally on that machine

This prevents random websites from silently gaining access to a user's local agent runtime.

More details are in [`docs/public/SECURITY.md`](./docs/public/SECURITY.md).

## Runtime Logs

Runtime logs are stored in:

- Windows: `%USERPROFILE%\\.local-agent-bridge\\runtime_logs`
- macOS / Linux: `~/.local-agent-bridge/runtime_logs`

Important files:

- `desktop_app.log`
- `bridge_server.log`

## Repository Layout

```text
WebAgent/
  docs/
  examples/
  server/
  widget/
  README.md
  CONTRIBUTING.md
  SECURITY.md
  LICENSE
```

Key folders:

- [`widget/`](./widget): embeddable widget package for websites
- [`server/`](./server): local bridge package and desktop companion
- [`examples/`](./examples): demo and host integration examples
- [`docs/public/`](./docs/public): public-facing setup, security, and deployment docs

`deprecated/` exists locally for archived reference material but is intentionally excluded from the public GitHub repo.

## Documentation

- [`docs/public/QUICKSTART.md`](./docs/public/QUICKSTART.md)
- [`docs/public/USAGE.md`](./docs/public/USAGE.md)
- [`docs/public/DEPLOYMENT.md`](./docs/public/DEPLOYMENT.md)
- [`docs/public/DOWNLOADS.md`](./docs/public/DOWNLOADS.md)
- [`docs/public/BRIDGE_CONTRACT.md`](./docs/public/BRIDGE_CONTRACT.md)
- [`docs/public/ARCHITECTURE.md`](./docs/public/ARCHITECTURE.md)
- [`docs/public/SECURITY.md`](./docs/public/SECURITY.md)
- [`docs/public/RELEASES.md`](./docs/public/RELEASES.md)

## Project Status

What is already in place:

- reusable embeddable widget
- Codex and Claude support
- widget-side progress and action flow
- local bridge auto-discovery
- local approval flow for website origins
- desktop companion app and Windows setup flow

What still needs more hardening:

- more automated test coverage
- stronger hosted-backend auth controls
- broader browser and host-site integration testing
- packaging polish across macOS and Linux

## Publishing

Suggested public distribution model:

- source code on GitHub
- widget package published from `widget/`
- Python package published from `server/`
- desktop binaries published through GitHub Releases

Current repo also includes ready-to-download packaged artifacts for immediate use:

- Windows installer and app under [`server/dist/windows/`](./server/dist/windows)
- Python wheel and source tarball under [`server/dist/`](./server/dist)
- widget npm tarball under [`widget/`](./widget)

Widget publish:

```bash
cd widget
npm publish --access public
```

Server publish:

```bash
cd server
python -m build
twine upload dist/*
```

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Security

See [`SECURITY.md`](./SECURITY.md).

## License

This project is licensed under the MIT License. See [`LICENSE`](./LICENSE).
