# Security Model

This project is only useful if it respects the browser-to-local-machine boundary.

## The Core Rule

A website script must not gain silent access to the user's local agent.

That is why the local bridge separates:

- discovery
- approval
- API access

## Discovery

The widget may call:

- `/.well-known/webagent-bridge`

This only tells the widget that a bridge exists and what base URL it should use.

Discovery alone does not grant permission to use the agent.

## Approval

When a website origin has not been approved yet:

- the bridge returns `approval_required`
- the widget can open the local approval page
- the user decides whether to allow that origin

Approvals are stored locally and can be managed from:

- `/bridge/sites`

Approval events are also appended to daily text logs:

- `~/.local-agent-bridge/approval_logs/approvals-YYYY-MM-DD.txt`

## API Gating

All `/api/*` routes are blocked for unapproved origins when local approval is enabled.

This means:

- a random website can detect that a bridge exists
- it cannot run Codex or Claude without approval

## Hosted Backend Mode

If a site sets `apiBaseUrl`, it can bypass local-agent discovery entirely and use its own backend.

That is intentional, but the security burden shifts to the site operator.

For hosted backends, you should add:

- authentication
- tenant isolation
- quotas
- audit logging
- stricter tool and action policies

## Recommended Defaults

For local-bridge mode:

- keep `WEBAGENT_REQUIRE_APPROVAL=1`
- bind to `127.0.0.1`
- do not expose the local bridge on a public interface

For hosted mode:

- do not allow anonymous production traffic
- validate origin and tenant identity
- harden all server-side tools separately

## Remaining Risks

This repo is strong enough for advanced prototypes and controlled deployments, but broad production use still needs:

- more automated security tests
- more granular action policy controls
- clearer user-facing trust prompts
- more robust hosted-backend auth and abuse controls
