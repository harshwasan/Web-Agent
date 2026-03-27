# Usage

This project has two audiences.

## Website Owners

Website owners use the widget package.

They are responsible for:

- adding the script to the page
- mounting the widget
- providing the host bridge
- deciding whether to let users use their own local bridge or force a site backend

### Website owner defaults

If the site does not set `apiBaseUrl`:

- the widget tries to use the user's local bridge

If the site sets `apiBaseUrl`:

- the widget uses the site backend instead

### Minimal example

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
    }
  };

  AgentWidget.init({
    target: "#agent-root",
    bridge: window.MySiteAgentBridge,
    defaultBackend: "codex"
  });
</script>
```

## End Users

End users use the local bridge package.

They are responsible for:

- installing `local-agent-bridge`
- running it on their machine
- approving websites they trust
- configuring local Codex or Claude executables if needed

### Local bridge defaults

- default host: `127.0.0.1`
- default port: `8787`
- default discovery URL: `http://127.0.0.1:8787/.well-known/webagent-bridge`
- default approval manager: `http://127.0.0.1:8787/bridge/sites`

## Hosted Backend Operators

Some teams may want to run their own backend and force the widget to use it.

They are responsible for:

- hosting the backend
- authentication
- tenant isolation
- quotas and abuse controls
- operational logging

Hosted mode is valid, but it is a different trust model from user-owned local-agent mode.
