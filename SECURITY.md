# Security Policy

## Supported Surface

The active security boundary for this project is the public layout:

- `widget/`
- `server/`
- `examples/`
- `docs/public/`

Archived material under `deprecated/` is not part of the intended public surface.

## Security Model

WebAgent is designed around a local approval boundary:

- the widget may discover a local bridge
- a website may not use the local bridge until the user approves that origin locally

Important consequences:

- do not weaken origin approval checks in the local bridge
- do not silently allow arbitrary websites to use local agent APIs
- do not expose dangerous website actions without clear approval and scope

## Reporting

If you find a security issue, report it privately to the project maintainers before opening a public issue.

When reporting, include:

- affected component
- reproduction steps
- impact
- whether the issue affects local-bridge mode, site-backend mode, or both

## Areas That Need Extra Care

- protocol handler behavior for `webagent://`
- localhost discovery and approval flow
- any bridge action that can click, type, fetch files, or export data
- hosted backend deployments that expose the bridge beyond localhost
