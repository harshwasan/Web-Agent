# Dealer Ops Demo Host

This is a static demo page used to test the WebAgent widget against a realistic website host.

## What the page supports

- A visible inventory table that can be filtered through `#inventory-search` and `#location-filter`
- Buttons the agent can safely click:
  - `#fill-lc200-btn`
  - `#refresh-inventory-btn`
  - `#open-maintenance-btn`
  - `#toggle-premium-btn`
- An Agent Workspace target at `#agent-workspace`
- A maintenance modal that can be opened and closed

## What to prefer

- Use website actions for host-specific UI work
- Use `renderAgentHtml` when you want to present structured results inside the workspace
- Read the attached `capabilities.json` and `api-client.js` files before making assumptions about supported selectors or demo APIs

## Notes

- The inventory rows are static demo data
- The "API" is illustrative and documented through the attached class file
- This host is meant for safe local testing, not real transactions
