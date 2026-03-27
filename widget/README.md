# `@webagent/widget`

Embeddable browser widget for websites that want a local agent side panel.

This package contains only the frontend script. It does not run Codex or Claude itself. By default it auto-discovers a user's `local-agent-bridge` on `localhost`. A host site can still override that by setting `apiBaseUrl`.

## Install

```bash
npm install @webagent/widget
```

Direct tarball committed in this repo:

```bash
npm install ./webagent-widget-0.1.0.tgz
```

Checksum file:

- [`SHA256SUMS.txt`](./SHA256SUMS.txt)

Or load the built script from a CDN:

```html
<script src="https://cdn.jsdelivr.net/npm/@webagent/widget/dist/agent-widget.js"></script>
```

## Host Requirements

The host page must provide:

- a DOM node to mount into
- a bridge object with at least `getContext()`

Optional:

- `apiBaseUrl` if the site wants to force its own backend instead of the user's local bridge

## Connection Precedence

The widget resolves backends in this order:

1. Site-provided `apiBaseUrl`
2. Auto-discovered local bridge
3. No connection

That means a site can force its own backend, but otherwise the user can use their own local bridge.

## Minimal Example

```html
<div id="agent-root"></div>
<div id="agent-workspace" data-agent-workspace="main"></div>

<script src="/node_modules/@webagent/widget/dist/agent-widget.js"></script>
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

With no `apiBaseUrl`, the widget tries `http://127.0.0.1:8787/.well-known/webagent-bridge` and `http://localhost:8787/.well-known/webagent-bridge` automatically.

If the local bridge requires approval for that site origin, the widget will surface the approval flow and prompt the user to approve the site locally.

## Bridge Contract

Required:

- `getContext(allowUiAccess)`

Recommended:

- `getVisibleTextSample()`

Optional action methods:

- `clickSelector(selector)`
- `setInputValue(selector, value)`
- `navigateStock(symbol)`
- `queryDb(sql, limit)`
- `exportQueryToCsv(sql, path)`
- `fetchDomHtml(offset, limit)`
- `renderAgentHtml(html)`
- `appendAgentHtml(html)`
- `webSearch(query, limit)`
- `fetchWebPage(url)`
- `fetchDbTables()`
- `fetchDbStatus()`

If a method is missing, the widget treats that action as unsupported.

## Config

Supported `AgentWidget.init({...})` options:

- `target`
- `bridge` or `agentBridge`
- `apiBaseUrl`
- `autoDetectLocalBridge`
- `localBridgeDiscoveryUrl` or `localBridgeDiscoveryUrls`
- `defaultBackend`
- `theme`
- `hostedDocs`
- `hostContext`
- `workspaceTarget`
- `storageNamespace`
- `storageScope`
- `autoInit`
- `cssVars` or `themeVars`

## Easy CSS Overrides

Host sites do not need to edit the widget file to restyle it. The widget now accepts CSS variable overrides directly through `AgentWidget.init(...)`.

```html
<script>
  AgentWidget.init({
    target: "#agent-root",
    bridge: window.MySiteAgentBridge,
    defaultBackend: "codex",
    cssVars: {
      "--cdx-shell-bg": "#0f1724",
      "--cdx-control-bg": "#0f1724",
      "--cdx-panel": "#131a25",
      "--cdx-border": "#314766",
      "--cdx-accent": "#22d3ee"
    }
  });
</script>
```

You can also set the same variables from your own stylesheet on `.codex-root` if you prefer CSS over JS config.

## Notes

- The widget expects a backend that matches the local bridge API shape.
- The widget can stream progress from both Codex and Claude endpoints.
- The widget can render host-approved HTML into an Agent Workspace through `renderAgentHtml` and `appendAgentHtml`.

## Example

See [examples/basic/index.html](./examples/basic/index.html).
