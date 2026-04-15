# WebAgent

Embeddable website agent widget backed by a user-run local bridge for Codex and Claude.

WebAgent is designed for sites that want agent-assisted workflows without moving the full runtime into the browser. The site embeds a widget and exposes a small, safe bridge API. The end user runs a local bridge on their own machine. That keeps agent execution user-controlled while still allowing the site to provide structured page actions, approvals, and context.

## Why This Exists

WebAgent is useful when you need:

- an embeddable agent UI that can stream progress and request approvals
- host-specific page actions exposed through a small JavaScript bridge
- local-first execution where the user controls the bridge runtime
- a clean separation between site UI, site actions, and agent execution

## Architecture

WebAgent has two main parts:

- [`widget/`](./widget): the embeddable browser widget
- [`server/`](./server): the local bridge and optional desktop companion

High-level flow:

1. A site embeds the widget.
2. The site provides a small bridge object for page context and allowed actions.
3. The widget connects to either:
   - the user's local bridge, or
   - a site-provided backend through `apiBaseUrl`
4. Codex or Claude runs through the selected backend.
5. The widget renders progress, approvals, and action results.

## Quick Start

### For site owners

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

If `apiBaseUrl` is omitted, the widget attempts local bridge discovery.

To force a site-hosted backend:

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
- current Windows binaries are unsigned, so SmartScreen or Smart App Control may warn or block them

macOS / Linux:

```bash
cd server
python3 -m pip install .
local-agent-bridge
```

Optional desktop companion after `pip install .`:

```bash
local-agent-bridge-app
```

Default local bridge address:

- `http://127.0.0.1:8787`

Local approval manager:

- `http://127.0.0.1:8787/bridge/sites`

## Security Model

The local bridge does not grant site access by default.

When a site first attempts to connect:

1. the bridge returns `approval_required`
2. the widget opens the local approval flow
3. the user explicitly allows or denies the site
4. the decision is stored locally on that machine

That prevents arbitrary sites from silently attaching to the user's local runtime.

More detail:

- [`docs/public/SECURITY.md`](./docs/public/SECURITY.md)

## Repository Layout

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
- [`examples/`](./examples): demo host and sample integrations
- [`docs/public/`](./docs/public): public-facing docs

## Packaging And Downloads

Current packaged artifacts in this repo:

- Windows installer and app in [`server/dist/windows/`](./server/dist/windows)
- Python wheel and source tarball in [`server/dist/`](./server/dist)
- widget npm tarball in [`widget/`](./widget)

Checksums:

- [`server/dist/SHA256SUMS.txt`](./server/dist/SHA256SUMS.txt)
- [`widget/SHA256SUMS.txt`](./widget/SHA256SUMS.txt)

Important:

- current Windows binaries are unsigned
- signed release builds are still pending
- macOS and Linux packaging is usable but less polished than the Windows flow

## Documentation

- [`docs/public/QUICKSTART.md`](./docs/public/QUICKSTART.md)
- [`docs/public/USAGE.md`](./docs/public/USAGE.md)
- [`docs/public/DOWNLOADS.md`](./docs/public/DOWNLOADS.md)
- [`docs/public/BRIDGE_CONTRACT.md`](./docs/public/BRIDGE_CONTRACT.md)
- [`docs/public/ARCHITECTURE.md`](./docs/public/ARCHITECTURE.md)
- [`docs/public/DEPLOYMENT.md`](./docs/public/DEPLOYMENT.md)
- [`docs/public/SECURITY.md`](./docs/public/SECURITY.md)
- [`docs/public/RELEASES.md`](./docs/public/RELEASES.md)

## Current Status

Already in place:

- embeddable widget package
- Codex and Claude support
- local bridge auto-discovery
- user approval flow for site access
- packaged Windows setup flow
- optional desktop companion

Still being improved:

- broader automated test coverage
- stronger hosted-backend auth controls
- broader integration testing across host sites and browsers
- more polished macOS and Linux packaging

## Recommended Demo Additions

The repository would benefit from:

- screenshots of the widget embedded on a host page
- a short GIF showing the approval flow
- a sequence diagram showing host page -> widget -> local bridge -> backend

## Contributing

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)

## License

- [`LICENSE`](./LICENSE)
