# Architecture

WebAgent is built around a simple separation of concerns.

## Components

### Widget

The widget is the browser UI.

Responsibilities:

- render the assistant panel
- collect conversation state
- gather host page context through the host bridge
- display progress and action approvals
- call either the local bridge or a hosted backend

The widget does not run local agent binaries.

### Host Bridge

The host bridge is a JavaScript object provided by the website.

Responsibilities:

- expose page context
- expose allowed UI actions
- define the safe capability boundary for that site

This is why the same widget can work across different websites.

### Local Agent Bridge

The local bridge is the companion service that runs on the user's machine.

Responsibilities:

- discoverable on `localhost`
- verify site approval
- expose API routes for Codex, Claude, optional DB helper, and web tools
- start and monitor local CLI processes

### Hosted Backend

Optional. A website can provide its own backend instead of relying on the user's local bridge.

Responsibilities:

- same API shape as the local bridge
- site-controlled authentication, logging, quotas, and tenancy

## Request Flow

### Local-agent mode

1. Site loads widget.
2. Widget asks the host bridge for page context.
3. Widget checks `/.well-known/webagent-bridge` on localhost.
4. Local bridge announces its `api_base_url`.
5. Widget calls `/api/codex/*` or `/api/claude/*`.
6. If the site is unapproved, the bridge returns `approval_required`.
7. User approves locally.
8. Requests proceed normally.

### Site-backend mode

1. Site loads widget.
2. Site sets `apiBaseUrl`.
3. Widget skips local discovery.
4. Widget talks directly to the site backend.

## Why Discovery Uses a Well-Known Endpoint

The widget needs one stable place to ask:

- is a bridge running
- what is its real base URL
- is this site approved

That is why discovery uses:

- `/.well-known/webagent-bridge`

This avoids random port scanning while still allowing the bridge to advertise the API base it wants used.

## Why the Host Bridge Matters

Without a host bridge, the model would only have generic DOM scraping.

With a host bridge, the website can provide:

- application-specific context
- safer action methods
- a stable integration surface even when the raw DOM changes

That is the main architectural reason this can be reused across websites rather than being a one-off automation script.
