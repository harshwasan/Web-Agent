# Deployment

There are two valid deployment models.

## Model A: User-Owned Local Bridge

This is the default design for this project.

### Shape

- website includes the widget
- website provides the host bridge
- widget auto-discovers the user's local bridge
- local bridge runs the user's own local Codex or Claude agent

### Pros

- user keeps control of their own agent
- no hosted model execution required from the website owner
- simple trust boundary: per-site local approval

### Requirements

- user installs `local-agent-bridge`
- local bridge is running on `localhost`
- user approves the website origin

Optional smoother local install:

- user runs `local-agent-bridge-install`
- this registers `webagent://`
- if localhost discovery fails, the widget can try `webagent://open-bridge`
- the installed or Python-run desktop companion can then start/focus the local bridge

### Current platform state

- Windows:
  packaged setup app exists today
- macOS:
  source-based install works best for now; the desktop companion is a Python-installed GUI helper, not a polished packaged `.app`
- Linux:
  source-based install works best today unless you build the setup bundle yourself; the desktop companion is a Python-installed GUI helper, not polished distro-native packaging

## Model B: Site-Hosted Backend

This is optional and explicit.

### Shape

- website includes the widget
- website provides the host bridge
- website sets `apiBaseUrl`
- widget skips local discovery and uses the site backend

### Pros

- centralized operations
- better fit for managed enterprise deployments
- website owner controls infra and policies

### Requirements

- hosted backend deployment
- authentication
- quotas
- tenant isolation
- logging and observability

## Discovery

The local bridge is discovered through a well-known endpoint:

- `/.well-known/webagent-bridge`

The widget probes a short fixed list:

- `http://127.0.0.1:8787/.well-known/webagent-bridge`
- `http://localhost:8787/.well-known/webagent-bridge`

The response includes the effective `api_base_url`.

This keeps discovery stable without forcing the widget to guess arbitrary ports.

## Local Approval Flow

When a new website tries to use the local bridge:

1. The site loads the widget.
2. The widget discovers the local bridge.
3. The widget sends a request to `/api/...`.
4. The bridge sees that the origin is unapproved.
5. The bridge responds with `approval_required` and an approval URL.
6. The user approves or denies locally.
7. Approved sites can use the bridge until revoked.

## Management

Local approvals can be managed at:

- `/bridge/sites`

That page supports:

- listing approved origins
- manual approval
- revocation

## Recommended Deployment Defaults

For local-agent mode:

- keep bridge bound to `127.0.0.1`
- keep local approval enabled
- do not expose the bridge publicly
- expose runtime logs for local troubleshooting

For hosted mode:

- require auth
- separate tenants
- audit tool usage
- restrict dangerous server-side tools
