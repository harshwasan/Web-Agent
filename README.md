# WebAgent

Embeddable agent UI for websites, backed by a user-run local bridge for Codex and Claude.

Use it when you want:

- a website widget that can show agent progress and ask for approvals
- host-specific page actions exposed through simple JavaScript
- end users to keep the actual agent runtime on their own machine

WebAgent has two parts:

- [`widget/`](./widget): the browser widget a website embeds
- [`server/`](./server): the local bridge and desktop companion the end user runs

That lets websites expose safe page-specific actions while users keep the agent runtime on their own machine.

## How It Works

1. A website embeds the widget.
2. The website provides a small JS bridge with page context and safe UI actions.
3. The widget connects to either:
   - the user's local bridge, or
   - a site-provided backend via `apiBaseUrl`
4. Codex or Claude runs through the backend.
5. The widget shows progress, asks for approval when needed, and executes allowed page actions.

## Quick Start

### For website owners

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

If you do not provide `apiBaseUrl`, the widget tries to auto-discover the user's local bridge.

If you want to force your own backend:

```js
AgentWidget.init({
  target: "#agent-root",
  bridge: window.MySiteAgentBridge,
  apiBaseUrl: "https://agent.example.com",
  defaultBackend: "codex"
});
```

### For end users

Windows:

- run [`server/dist/windows/WebAgentBridgeSetup.exe`](./server/dist/windows/WebAgentBridgeSetup.exe)
- current Windows binaries in this repo are unsigned, so Windows SmartScreen / Smart App Control may warn or block them

macOS / Linux:

```bash
cd server
python3 -m pip install .
local-agent-bridge
```

Optional desktop companion:

```bash
local-agent-bridge-app
```

Default local address:

- `http://127.0.0.1:8787`

Approval manager:

- `http://127.0.0.1:8787/bridge/sites`

Direct packaged downloads are listed in [`docs/public/DOWNLOADS.md`](./docs/public/DOWNLOADS.md).

## Security

The local bridge does not grant agent access to a website by default.

When a site first tries to connect:

1. the bridge returns `approval_required`
2. the widget opens the local approval flow
3. the user allows or denies the site
4. the decision is stored locally on that machine

That prevents random websites from silently gaining access to the user's local agent runtime.

More detail:

- [`docs/public/SECURITY.md`](./docs/public/SECURITY.md)

## Downloads

Current packaged artifacts in this repo:

- Windows installer and app in [`server/dist/windows/`](./server/dist/windows)
- Python wheel and source tarball in [`server/dist/`](./server/dist)
- widget npm tarball in [`widget/`](./widget)

Important:

- current Windows binaries are unsigned
- that can trigger Windows SmartScreen or Smart App Control warnings
- signed Windows release builds are still pending

Checksums:

- [`server/dist/SHA256SUMS.txt`](./server/dist/SHA256SUMS.txt)
- [`widget/SHA256SUMS.txt`](./widget/SHA256SUMS.txt)

## Documentation

- [`docs/public/QUICKSTART.md`](./docs/public/QUICKSTART.md)
- [`docs/public/USAGE.md`](./docs/public/USAGE.md)
- [`docs/public/DOWNLOADS.md`](./docs/public/DOWNLOADS.md)
- [`docs/public/BRIDGE_CONTRACT.md`](./docs/public/BRIDGE_CONTRACT.md)
- [`docs/public/ARCHITECTURE.md`](./docs/public/ARCHITECTURE.md)
- [`docs/public/DEPLOYMENT.md`](./docs/public/DEPLOYMENT.md)
- [`docs/public/SECURITY.md`](./docs/public/SECURITY.md)
- [`docs/public/RELEASES.md`](./docs/public/RELEASES.md)

## Repo Layout

```text
WebAgent/
  docs/
  examples/
  server/
  widget/
```

Key folders:

- [`widget/`](./widget): embeddable widget package
- [`server/`](./server): local bridge and desktop companion
- [`examples/`](./examples): demo host and reference examples
- [`docs/public/`](./docs/public): public-facing docs

## Project Status

Already in place:

- reusable embeddable widget
- Codex and Claude support
- widget-side progress and action flow
- local bridge auto-discovery
- local website approval flow
- Windows setup flow and desktop companion

Still needs more hardening:

- more automated test coverage
- stronger hosted-backend auth controls
- broader browser and host-site integration testing
- more polished macOS and Linux packaging

## Contributing

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)

## License

- [`LICENSE`](./LICENSE)
